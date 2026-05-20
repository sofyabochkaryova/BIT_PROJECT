from decimal import Decimal
from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from contracts.models import Contract
from notifications.views import create_notification
from requests_app.models import ServiceRequest
from .generators import generate_document
from .models import BusinessDocument, DocumentSignature


# Допустимые переходы статуса документа
DOCUMENT_TRANSITIONS = {
	'draft': ['issued'],
	'issued': ['approved', 'cancelled'],
	'approved': ['signed', 'cancelled'],
	'signed': ['paid', 'cancelled'],
	'paid': [],
	'cancelled': ['draft'],
}


@login_required
def document_list(request):
	documents = BusinessDocument.objects.select_related('request', 'contract', 'proposal').order_by('-created_at')

	if hasattr(request.user, 'profile') and request.user.profile.is_client:
		documents = documents.filter(request__client=request.user)

	return render(request, 'documents/list.html', {'documents': documents})


@login_required
def document_detail(request, pk):
	document = get_object_or_404(BusinessDocument.objects.select_related('request', 'contract', 'proposal'), pk=pk)

	profile = getattr(request.user, 'profile', None)
	role = getattr(profile, 'role', None)

	can_view = (
		document.request.client == request.user
		or (role in ['analyst', 'admin'])
	)
	if not can_view:
		messages.error(request, 'Доступ запрещён')
		return redirect('accounts:dashboard')

	can_manage = role in ['analyst', 'admin']

	if request.method == 'POST' and can_manage:
		new_status = request.POST.get('status')
		if new_status:
			allowed = DOCUMENT_TRANSITIONS.get(document.status, [])
			if new_status in allowed:
				document.status = new_status
				document.save(update_fields=['status', 'updated_at'])

				# При оплате счёта — можно перевести заявку дальше
				if new_status == 'paid' and document.doc_type == 'invoice':
					sr = document.request
					if sr.status == 'CONTRACT_SIGNED':
						try:
							sr.change_status('ADVANCE_PAYMENT', request.user, f'Оплачен счёт {document.number}')
						except ValueError:
							pass

				messages.success(request, f'Статус документа: {document.get_status_display()}')
			else:
				messages.error(request, 'Недопустимый переход статуса')
			return redirect('documents:detail', pk=pk)

	allowed_transitions = DOCUMENT_TRANSITIONS.get(document.status, [])
	status_labels = dict(BusinessDocument.STATUS_CHOICES)

	signatures = document.signatures.select_related('signer').all()
	pending_signature = None
	if request.user == document.request.client:
		pending_signature = document.signatures.filter(signer=request.user, status='pending').first()

	return render(request, 'documents/detail.html', {
		'document': document,
		'can_manage': can_manage,
		'allowed_transitions': [(s, status_labels.get(s, s)) for s in allowed_transitions],
		'signatures': signatures,
		'pending_signature': pending_signature,
	})


@login_required
def generate_bundle(request, request_id):
	service_request = get_object_or_404(ServiceRequest, pk=request_id)
	if not hasattr(request.user, 'profile') or request.user.profile.role not in ['analyst', 'admin']:
		messages.error(request, 'Генерация пакета документов доступна только аналитикам и администраторам')
		return redirect('requests_app:request_detail', pk=request_id)

	# Проверка: если уже есть акт или счет, не создаём новые
	existing_act = service_request.business_documents.filter(doc_type='act').exists()
	existing_invoice = service_request.business_documents.filter(doc_type='invoice').exists()
	
	if existing_act and existing_invoice:
		messages.warning(request, 'По этой заявке уже созданы акт и счёт. Новые документы не будут созданы.')
		return redirect('documents:list')
	
	if existing_act or existing_invoice:
		messages.warning(request, 'По этой заявке уже создан акт или счёт. Проверьте существующие документы.')
		return redirect('documents:list')

	contract = service_request.contracts.order_by('-created_at').first()
	proposal = service_request.proposals.order_by('-created_at').first()

	amount = Decimal('0')
	if contract:
		amount = contract.amount or Decimal('0')
	elif proposal:
		amount = proposal.total_amount or Decimal('0')
	elif service_request.budget_to:
		amount = service_request.budget_to

	today = timezone.now().date()

	act = BusinessDocument(
		request=service_request,
		contract=contract,
		proposal=proposal,
		doc_type='act',
		title=f'Акт выполненных работ по заявке {service_request.number}',
		amount=amount,
		description='Подтверждение выполненных работ согласно объёму договора.',
		status='issued',
		issue_date=today,
		due_date=today,
		created_by=request.user,
	)
	act.save()

	invoice = BusinessDocument(
		request=service_request,
		contract=contract,
		proposal=proposal,
		doc_type='invoice',
		title=f'Счёт на оплату по заявке {service_request.number}',
		amount=amount,
		description='Оплата по этапу согласно договору/КП.',
		status='issued',
		issue_date=today,
		due_date=today + timedelta(days=5),
		created_by=request.user,
	)
	invoice.save()

	# Сразу создаём запросы подписи клиенту для акта и счёта
	DocumentSignature.objects.get_or_create(document=act, signer=service_request.client)
	DocumentSignature.objects.get_or_create(document=invoice, signer=service_request.client)

	create_notification(
		recipient=service_request.client,
		title='Документы на подписание',
		message=f'По заявке {service_request.number} сформированы акт и счёт. Подпишите документы в личном кабинете.',
		notification_type='request',
		sender=request.user,
		link=f'/documents/{act.pk}/',
	)

	messages.success(request, f'Пакет документов создан: {act.number}, {invoice.number}')
	return redirect('documents:list')


# ═══════════════════════════════════════════════════════════════════════════
#  Скачивание документов (только Word)
# ═══════════════════════════════════════════════════════════════════════════

@login_required
def download_document(request, pk):
	"""Скачать документ в формате docx."""
	document = get_object_or_404(BusinessDocument.objects.select_related(
		'request', 'contract', 'proposal',
	), pk=pk)

	profile = getattr(request.user, 'profile', None)
	role = getattr(profile, 'role', None)
	can_view = (
		document.request.client == request.user
		or (role in ['analyst', 'admin'])
	)
	if not can_view:
		messages.error(request, 'Доступ запрещён')
		return redirect('accounts:dashboard')

	try:
		buf, content_type, filename = generate_document(document, 'docx')
	except ValueError as exc:
		messages.error(request, str(exc))
		return redirect('documents:detail', pk=pk)

	response = HttpResponse(buf.read(), content_type=content_type)
	response['Content-Disposition'] = f'attachment; filename="{filename}"'
	return response


# ═══════════════════════════════════════════════════════════════════════════
#  Отправка документа на подписание клиенту
# ═══════════════════════════════════════════════════════════════════════════

@login_required
def send_for_signing(request, pk):
	"""Отправить документ клиенту на подписание."""
	document = get_object_or_404(BusinessDocument.objects.select_related('request'), pk=pk)

	profile = getattr(request.user, 'profile', None)
	role = getattr(profile, 'role', None)
	if role not in ['analyst', 'admin']:
		messages.error(request, 'Только аналитик или администратор может отправлять на подписание')
		return redirect('documents:detail', pk=pk)

	client = document.request.client

	# Создаём/переиспользуем запись подписания без нарушения unique(document, signer)
	sig, created = DocumentSignature.objects.get_or_create(
		document=document,
		signer=client,
		defaults={'status': 'pending'},
	)

	if not created and sig.status == 'pending':
		messages.warning(request, 'Документ уже отправлен клиенту на подписание')
		return redirect('documents:detail', pk=pk)

	if not created and sig.status != 'pending':
		sig.status = 'pending'
		sig.comment = ''
		sig.signed_at = None
		sig.ip_address = None
		sig.save(update_fields=['status', 'comment', 'signed_at', 'ip_address'])

	# Переводим документ в статус «Выставлен», если черновик
	if document.status == 'draft':
		document.status = 'issued'
		document.issue_date = timezone.now().date()
		document.save(update_fields=['status', 'issue_date', 'updated_at'])

	# Уведомляем клиента
	create_notification(
		recipient=client,
		title='Документ на подписание',
		message=f'{document.get_doc_type_display()} {document.number} ожидает вашей подписи',
		notification_type='request',
		sender=request.user,
		link=f'/documents/{document.pk}/',
	)

	messages.success(request, f'Документ {document.number} отправлен на подписание клиенту {client.get_full_name() or client.username}')
	return redirect('documents:detail', pk=pk)


# ═══════════════════════════════════════════════════════════════════════════
#  Подписание документа клиентом
# ═══════════════════════════════════════════════════════════════════════════

@login_required
def sign_document(request, pk):
	"""Клиент подписывает документ."""
	document = get_object_or_404(BusinessDocument.objects.select_related('request'), pk=pk)

	sig = document.signatures.filter(signer=request.user, status='pending').first()
	if not sig:
		messages.error(request, 'Нет активного запроса на подписание')
		return redirect('documents:detail', pk=pk)

	if request.method != 'POST':
		return redirect('documents:detail', pk=pk)

	action = request.POST.get('sign_action', 'sign')
	comment = request.POST.get('sign_comment', '')

	if action == 'reject':
		sig.status = 'rejected'
		sig.comment = comment
		sig.signed_at = timezone.now()
		sig.ip_address = _get_client_ip(request)
		sig.save(update_fields=['status', 'comment', 'signed_at', 'ip_address'])

		# Уведомляем аналитика / создателя документа
		if document.created_by:
			create_notification(
				recipient=document.created_by,
				title='Документ отклонён',
				message=f'{document.number} отклонён клиентом: {comment[:100]}',
				notification_type='request',
				sender=request.user,
				link=f'/documents/{document.pk}/',
			)

		messages.info(request, 'Документ отклонён')
		return redirect('documents:detail', pk=pk)

	# Подписание
	sig.status = 'signed'
	sig.comment = comment
	sig.signed_at = timezone.now()
	sig.ip_address = _get_client_ip(request)
	sig.save(update_fields=['status', 'comment', 'signed_at', 'ip_address'])

	# Переводим документ в «Подписан»
	if document.status in ('issued', 'approved'):
		document.status = 'signed'
		document.save(update_fields=['status', 'updated_at'])

	# Если тип — договор, синхронизируем контракт
	if document.doc_type == 'contract' and document.contract:
		contract = document.contract
		if contract.status in ('draft', 'legal_review', 'sent'):
			contract.status = 'signed'
			contract.save(update_fields=['status', 'updated_at'])
			sr = document.request
			try:
				sr.change_status('CONTRACT_SIGNED', request.user, f'Договор {contract.number} подписан клиентом')
			except (ValueError, AttributeError):
				pass

	# Уведомляем создателя документа
	if document.created_by:
		create_notification(
			recipient=document.created_by,
			title='Документ подписан!',
			message=f'{document.number} подписан клиентом',
			notification_type='request',
			sender=request.user,
			link=f'/documents/{document.pk}/',
		)

	messages.success(request, f'Документ {document.number} успешно подписан')
	return redirect('documents:detail', pk=pk)


@login_required
def sign_by_token(request, token):
	"""Подписание документа по токену (из ссылки в уведомлении)."""
	sig = get_object_or_404(DocumentSignature.objects.select_related('document', 'signer'), token=token)

	if sig.signer != request.user:
		messages.error(request, 'Токен подписания не соответствует вашему аккаунту')
		return redirect('accounts:dashboard')

	return redirect('documents:detail', pk=sig.document.pk)


def _get_client_ip(request):
	"""Извлекает IP-адрес клиента."""
	x_forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
	if x_forwarded:
		return x_forwarded.split(',')[0].strip()
	return request.META.get('REMOTE_ADDR')


@login_required
def company_stamp_settings(request):
	"""Загрузка печати и подписи компании (ООО БИТ)."""
	import os
	from django.conf import settings as django_settings

	profile = getattr(request.user, 'profile', None)
	role = getattr(profile, 'role', None)
	if role not in ['analyst', 'admin']:
		messages.error(request, 'Доступ запрещён')
		return redirect('accounts:dashboard')

	company_dir = os.path.join(django_settings.MEDIA_ROOT, 'company')
	os.makedirs(company_dir, exist_ok=True)

	stamp_path = os.path.join(company_dir, 'stamp.png')
	signature_path = os.path.join(company_dir, 'signature.png')

	if request.method == 'POST':
		stamp_file = request.FILES.get('stamp')
		signature_file = request.FILES.get('signature')

		if stamp_file:
			with open(stamp_path, 'wb') as f:
				for chunk in stamp_file.chunks():
					f.write(chunk)
			messages.success(request, 'Печать загружена')

		if signature_file:
			with open(signature_path, 'wb') as f:
				for chunk in signature_file.chunks():
					f.write(chunk)
			messages.success(request, 'Подпись загружена')

		if not stamp_file and not signature_file:
			messages.warning(request, 'Выберите файл для загрузки')

		return redirect('documents:company_stamp')

	has_stamp = os.path.isfile(stamp_path)
	has_signature = os.path.isfile(signature_path)

	return render(request, 'documents/company_stamp.html', {
		'has_stamp': has_stamp,
		'has_signature': has_signature,
		'stamp_url': django_settings.MEDIA_URL + 'company/stamp.png' if has_stamp else None,
		'signature_url': django_settings.MEDIA_URL + 'company/signature.png' if has_signature else None,
	})
