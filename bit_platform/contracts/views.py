from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from notifications.views import create_notification
from proposals.models import CommercialProposal
from requests_app.models import ServiceRequest
from core.pipeline import auto_create_project
from .models import Contract


# Допустимые переходы статуса договора
CONTRACT_TRANSITIONS = {
	'draft': ['sent'],
	'sent': ['signed', 'draft'],
	'signed': ['active', 'terminated'],
	'active': ['closed', 'terminated'],
	'closed': [],
	'terminated': ['draft'],
}

# Маппинг статуса договора → статуса заявки
CONTRACT_TO_REQUEST_STATUS = {
	'sent': 'CONTRACT_SENT',
	'signed': 'CONTRACT_SIGNED',
	'active': 'CONVERTED',
}


@login_required
def contract_list(request):
	contracts = Contract.objects.select_related('request', 'proposal', 'responsible').order_by('-created_at')

	if hasattr(request.user, 'profile') and request.user.profile.is_client:
		contracts = contracts.filter(request__client=request.user)

	return render(request, 'contracts/list.html', {'contracts': contracts})


@login_required
def contract_detail(request, pk):
	contract = get_object_or_404(Contract.objects.select_related('request', 'proposal'), pk=pk)

	profile = getattr(request.user, 'profile', None)
	role = getattr(profile, 'role', None)

	can_view = (
		contract.request.client == request.user
		or contract.responsible == request.user
		or (role in ['analyst', 'admin'])
	)
	if not can_view:
		messages.error(request, 'Доступ запрещён')
		return redirect('accounts:dashboard')

	can_manage = role in ['analyst', 'admin']
	is_client = (contract.request.client == request.user)

	if request.method == 'POST':
		action = request.POST.get('action', 'change_status')

		if action == 'edit_contract' and can_manage:
			if contract.status not in ['draft', 'terminated']:
				messages.error(request, 'Редактировать можно только договор в статусе «Черновик» или «Расторгнут»')
				return redirect('contracts:detail', pk=pk)

			subject = (request.POST.get('subject') or '').strip()
			amount_raw = (request.POST.get('amount') or '').strip()
			if not subject:
				messages.error(request, 'Укажите предмет договора')
				return redirect('contracts:detail', pk=pk)

			try:
				amount = Decimal(amount_raw) if amount_raw else Decimal('0')
			except Exception:
				messages.error(request, 'Некорректная сумма договора')
				return redirect('contracts:detail', pk=pk)

			contract.subject = subject
			contract.amount = amount
			contract.start_date = request.POST.get('start_date') or None
			contract.end_date = request.POST.get('end_date') or None
			contract.payment_terms = request.POST.get('payment_terms', '').strip()
			update_fields = ['subject', 'amount', 'start_date', 'end_date', 'payment_terms', 'updated_at']
			if contract.status == 'terminated':
				contract.status = 'draft'
				update_fields.append('status')
			contract.save(update_fields=update_fields)

			# Обновляем связанный документ договора (если уже сформирован)
			from documents.models import BusinessDocument
			BusinessDocument.objects.filter(request=contract.request, contract=contract, doc_type='contract').update(
				title=f'Договор {contract.number}',
				amount=contract.amount,
				description=contract.subject,
				due_date=contract.end_date,
				updated_at=timezone.now(),
			)

			messages.success(request, 'Договор обновлён. Можно отправлять клиенту повторно.')
			return redirect('contracts:detail', pk=pk)

		# Клиент подписывает или отклоняет договор
		if action == 'client_sign' and is_client and contract.status == 'sent':
			decision = request.POST.get('decision')
			if decision == 'sign':
				contract.status = 'signed'
				contract.save(update_fields=['status', 'updated_at'])
				# Синхронизируем заявку
				sr = contract.request
				try:
					sr.change_status('CONTRACT_SIGNED', request.user, f'Клиент подписал договор {contract.number}', force=True)
				except (ValueError, Exception):
					pass
				# Обновляем DocumentSignature
				from documents.models import DocumentSignature
				DocumentSignature.objects.filter(
					document__contract=contract,
					signer=request.user,
					status='pending',
				).update(status='signed', signed_at=timezone.now())
				# Авто-создание проекта
				try:
					auto_create_project(contract, request.user)
				except Exception:
					messages.warning(request, 'Не удалось автоматически создать проект. Вы можете создать его вручную.')
				# Уведомляем аналитика
				if contract.responsible:
					create_notification(
						recipient=contract.responsible,
						title='Договор подписан клиентом',
						message=f'Клиент подписал договор {contract.number}',
						notification_type='request',
						sender=request.user,
						link=f'/contracts/{contract.pk}/',
					)
				messages.success(request, 'Договор подписан!')
			elif decision == 'reject':
				contract.status = 'terminated'
				contract.save(update_fields=['status', 'updated_at'])
				# Возвращаем заявку на этап согласования (договор отменён клиентом)
				sr = contract.request
				try:
					sr.change_status('NEGOTIATION', request.user, f'Клиент отклонил договор {contract.number}', force=True)
				except (ValueError, Exception):
					pass
				if contract.responsible:
					create_notification(
						recipient=contract.responsible,
						title='Договор отклонён клиентом',
						message=f'Клиент отклонил договор {contract.number}',
						notification_type='request',
						sender=request.user,
						link=f'/contracts/{contract.pk}/',
					)
				messages.warning(request, 'Договор отклонён')
			return redirect('contracts:detail', pk=pk)

		if not can_manage:
			messages.error(request, 'Недостаточно прав')
			return redirect('contracts:detail', pk=pk)

		# Ручное создание проекта
		if action == 'create_project' and can_manage:
			if not contract.request.projects.exists():
				try:
					project = auto_create_project(contract, request.user)
					if project:
						messages.success(request, f'Проект «{project.name}» успешно создан')
					else:
						messages.warning(request, 'Не удалось создать проект')
				except Exception as e:
					messages.error(request, f'Ошибка при создании проекта: {e}')
			else:
				messages.info(request, 'Проект уже создан')
			return redirect('contracts:detail', pk=pk)

		new_status = request.POST.get('status')

		if new_status:
			allowed = CONTRACT_TRANSITIONS.get(contract.status, [])
			if new_status not in allowed:
				messages.error(request, 'Недопустимый переход статуса договора')
				return redirect('contracts:detail', pk=pk)

			old_status = contract.status
			contract.status = new_status
			contract.save(update_fields=['status', 'updated_at'])

			# Синхронизируем статус заявки
			sr = contract.request
			target_request_status = CONTRACT_TO_REQUEST_STATUS.get(new_status)
			if target_request_status:
				try:
					sr.change_status(target_request_status, request.user, f'Договор {contract.number}: {contract.get_status_display()}', force=True)
				except (ValueError, Exception):
					pass  # Переход заявки невозможен, не блокируем

			# При отправке договора — создаём бизнес-документ для скачивания клиентом
			if new_status == 'sent':
				from documents.models import BusinessDocument
				from documents.models import DocumentSignature
				existing_doc = BusinessDocument.objects.filter(
					request=sr, contract=contract, doc_type='contract'
				).first()
				if not existing_doc:
					biz_doc = BusinessDocument(
						request=sr,
						contract=contract,
						proposal=contract.proposal,
						doc_type='contract',
						title=f'Договор {contract.number}',
						amount=contract.amount,
						description=contract.subject,
						status='issued',
						issue_date=timezone.now().date(),
						due_date=contract.end_date,
						created_by=request.user,
					)
					biz_doc.save()
				else:
					# Повторная отправка после правок: синхронизируем данные документа договора
					existing_doc.title = f'Договор {contract.number}'
					existing_doc.amount = contract.amount
					existing_doc.description = contract.subject
					existing_doc.due_date = contract.end_date
					existing_doc.status = 'issued'
					existing_doc.issue_date = timezone.now().date()
					existing_doc.save(update_fields=['title', 'amount', 'description', 'due_date', 'status', 'issue_date', 'updated_at'])
					biz_doc = existing_doc

				# Отправляем документ на подписание клиенту (без дублей)
				signature, created = DocumentSignature.objects.get_or_create(
					document=biz_doc,
					signer=sr.client,
					defaults={'status': 'pending'},
				)
				if not created and signature.status != 'pending':
					signature.status = 'pending'
					signature.comment = ''
					signature.signed_at = None
					signature.ip_address = None
					signature.save(update_fields=['status', 'comment', 'signed_at', 'ip_address'])

				create_notification(
					recipient=sr.client,
					title='Договор отправлен на подписание',
					message=f'Договор {contract.number} готов к подписанию. Скачайте, подпишите и отправьте в личном кабинете.',
					notification_type='request',
					sender=request.user,
					link=f'/contracts/{contract.pk}/',
				)

			# При подписании договора — авто-создание проекта и задач
			if new_status == 'signed':
				auto_create_project(contract, request.user)

			# При активации — уведомляем клиента
			if new_status == 'active':
				create_notification(
					recipient=sr.client,
					title='Проект запущен',
					message=f'Договор {contract.number} — проект переведён в работу',
					notification_type='request',
					sender=request.user,
					link=f'/requests/{sr.pk}/',
				)

			messages.success(request, f'Статус договора изменён: {contract.get_status_display()}')
			return redirect('contracts:detail', pk=pk)

	allowed_transitions = CONTRACT_TRANSITIONS.get(contract.status, [])
	status_labels = dict(Contract.STATUS_CHOICES)

	# Найти связанные проекты
	projects = contract.request.projects.all()

	return render(request, 'contracts/detail.html', {
		'contract': contract,
		'can_manage': can_manage,
		'is_client': is_client,
		'allowed_transitions': [(s, status_labels.get(s, s)) for s in allowed_transitions],
		'projects': projects,
	})


@login_required
def create_contract(request, request_id):
	service_request = get_object_or_404(ServiceRequest, pk=request_id)
	proposal = service_request.proposals.filter(status='accepted').order_by('-created_at').first()
	if not proposal:
		proposal = service_request.proposals.order_by('-created_at').first()

	if not hasattr(request.user, 'profile') or request.user.profile.role not in ['analyst', 'admin']:
		messages.error(request, 'Создавать договоры могут только аналитики и администраторы')
		return redirect('requests_app:request_detail', pk=request_id)

	if request.method == 'POST':
		if proposal and proposal.total_amount:
			amount = proposal.total_amount
		else:
			amount_raw = request.POST.get('amount')
			if amount_raw:
				try:
					amount = Decimal(amount_raw)
				except Exception:
					amount = Decimal('0')
			elif service_request.budget_to:
				amount = service_request.budget_to
			else:
				amount = Decimal('0')

		if amount <= 0 and proposal and proposal.total_amount:
			amount = proposal.total_amount

		contract = Contract(
			request=service_request,
			proposal=proposal,
			responsible=request.user,
			subject=request.POST.get('subject') or f'Оказание услуг по заявке {service_request.number}',
			amount=amount,
			start_date=request.POST.get('start_date') or None,
			end_date=request.POST.get('end_date') or None,
			payment_terms=request.POST.get('payment_terms', ''),
			status='draft',
		)
		contract.save()

		service_request.status = 'CONTRACT_DRAFT'
		service_request.save(update_fields=['status', 'updated_at'])

		messages.success(request, 'Договор создан')
		return redirect('contracts:detail', pk=contract.pk)

	return render(request, 'contracts/create.html', {'request_obj': service_request, 'proposal': proposal})
