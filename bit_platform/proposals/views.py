from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.mail import send_mail
from django.conf import settings
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from requests_app.models import ServiceRequest
from notifications.views import create_notification
from core.pipeline import estimate_stages, adapt_to_budget, suggest_team_for_request
from .models import CommercialProposal, ProposalItem


# Допустимые переходы статуса КП
PROPOSAL_TRANSITIONS = {
	'draft': ['sent'],
	'sent': ['accepted', 'rejected', 'draft'],
	'accepted': [],
	'rejected': ['draft'],
}


@login_required
def proposal_list(request):
	proposals = CommercialProposal.objects.select_related('request', 'author').order_by('-created_at')

	if hasattr(request.user, 'profile') and request.user.profile.is_client:
		proposals = proposals.filter(request__client=request.user)
	elif hasattr(request.user, 'profile') and request.user.profile.is_executor:
		proposals = proposals.filter(request__executor=request.user)

	return render(request, 'proposals/list.html', {'proposals': proposals})


@login_required
def proposal_detail(request, pk):
	proposal = get_object_or_404(
		CommercialProposal.objects.select_related('request', 'author', 'request__client').prefetch_related('items'),
		pk=pk,
	)

	profile = getattr(request.user, 'profile', None)
	role = getattr(profile, 'role', None)

	can_view = (
		proposal.request.client == request.user
		or proposal.author == request.user
		or (role in ['analyst', 'admin'])
	)
	if not can_view:
		messages.error(request, 'Доступ запрещён')
		return redirect('accounts:dashboard')

	can_manage = role in ['analyst', 'admin']
	can_client_decide = (proposal.request.client == request.user and proposal.status == 'sent')

	if request.method == 'POST':
		action = request.POST.get('action')

		if action == 'change_status' and can_manage:
			new_status = request.POST.get('status')
			allowed = PROPOSAL_TRANSITIONS.get(proposal.status, [])
			if new_status in allowed:
				proposal.status = new_status
				proposal.save(update_fields=['status', 'updated_at'])

				# Синхронизируем статус заявки
				sr = proposal.request
				if new_status == 'sent' and sr.status in ('PROPOSAL_DRAFT', 'IN_ANALYSIS', 'ESTIMATION'):
					sr.change_status('PROPOSAL_SENT', request.user, f'КП {proposal.number} отправлено клиенту')

					# Автоматически создаём бизнес-документ КП для скачивания клиентом
					from documents.models import BusinessDocument
					existing_doc = BusinessDocument.objects.filter(
						request=sr, proposal=proposal, doc_type='proposal'
					).first()
					if not existing_doc:
						biz_doc = BusinessDocument(
							request=sr,
							proposal=proposal,
							doc_type='proposal',
							title=f'Коммерческое предложение {proposal.number}',
							amount=proposal.total_amount,
							description=proposal.scope,
							status='issued',
							issue_date=timezone.now().date(),
							due_date=proposal.valid_until,
							created_by=request.user,
						)
						biz_doc.save()

					create_notification(
						recipient=sr.client,
						title='Получено коммерческое предложение',
						message=f'По заявке {sr.number} подготовлено КП {proposal.number} на сумму {proposal.total_amount} ₽. Скачайте документ в личном кабинете.',
						notification_type='request',
						sender=request.user,
						link=f'/proposals/{proposal.pk}/',
					)
					# Отправляем email клиенту
					client_email = sr.contact_email or sr.client.email
					if client_email:
						try:
							send_mail(
								subject=f'ООО «БИТ» — коммерческое предложение по заявке {sr.number}',
								message=(
									f'Здравствуйте, {sr.client.get_full_name() or sr.client.username}!\n\n'
									f'Ваша заявка {sr.number} принята в работу.\n'
									f'По ней подготовлено коммерческое предложение {proposal.number} '
									f'на сумму {proposal.total_amount:,.2f} ₽.\n\n'
									f'Ознакомьтесь с КП и примите решение в личном кабинете:\n'
									f'{settings.SITE_URL}/proposals/{proposal.pk}/\n\n'
									f'С уважением,\nКоманда ООО «БИТ»'
								),
								from_email=settings.DEFAULT_FROM_EMAIL,
								recipient_list=[client_email],
								fail_silently=True,
							)
						except Exception:
							pass  # Не блокируем основной процесс
				elif new_status == 'accepted' and sr.status in ('PROPOSAL_SENT', 'CLIENT_REVIEW', 'NEGOTIATION'):
					sr.change_status('CLIENT_APPROVED', request.user, f'Клиент принял КП {proposal.number}')

				messages.success(request, f'Статус КП изменён: {proposal.get_status_display()}')
			else:
				messages.error(request, 'Недопустимый переход статуса КП')
			return redirect('proposals:detail', pk=pk)

		elif action == 'client_accept' and can_client_decide:
			proposal.status = 'accepted'
			proposal.save(update_fields=['status', 'updated_at'])
			sr = proposal.request
			if sr.status in ('PROPOSAL_SENT', 'CLIENT_REVIEW', 'NEGOTIATION'):
				sr.change_status('CLIENT_APPROVED', request.user, f'Клиент принял КП {proposal.number}', force=True)
			create_notification(
				recipient=proposal.author,
				title='КП принято клиентом',
				message=f'Клиент {request.user.get_full_name()} принял КП {proposal.number}',
				notification_type='request',
				sender=request.user,
				link=f'/proposals/{proposal.pk}/',
			)
			messages.success(request, 'Вы приняли коммерческое предложение')
			return redirect('proposals:detail', pk=pk)

		elif action == 'client_reject' and can_client_decide:
			proposal.status = 'rejected'
			proposal.save(update_fields=['status', 'updated_at'])
			sr = proposal.request
			create_notification(
				recipient=proposal.author,
				title='КП отклонено клиентом',
				message=f'Клиент {request.user.get_full_name()} отклонил КП {proposal.number}',
				notification_type='request',
				sender=request.user,
				link=f'/proposals/{proposal.pk}/',
			)
			messages.success(request, 'Вы отклонили коммерческое предложение')
			return redirect('proposals:detail', pk=pk)

	allowed_transitions = PROPOSAL_TRANSITIONS.get(proposal.status, [])
	status_labels = dict(CommercialProposal.STATUS_CHOICES)

	return render(request, 'proposals/detail.html', {
		'proposal': proposal,
		'can_manage': can_manage,
		'can_client_decide': can_client_decide,
		'allowed_transitions': [(s, status_labels.get(s, s)) for s in allowed_transitions],
	})


@login_required
def create_proposal(request, request_id):
	service_request = get_object_or_404(ServiceRequest, pk=request_id)

	if not hasattr(request.user, 'profile') or request.user.profile.role not in ['analyst', 'admin']:
		messages.error(request, 'Создавать КП могут только аналитики и администраторы')
		return redirect('requests_app:request_detail', pk=request_id)

	if request.method == 'POST':
		proposal = CommercialProposal(
			request=service_request,
			author=request.user,
			title=request.POST.get('title') or f'КП по заявке {service_request.number}',
			scope=request.POST.get('scope', ''),
			assumptions='',
			duration_days=0,
			valid_until=request.POST.get('valid_until') or None,
			status='draft',
		)
		proposal.save()  # number генерируется в save()

		stages = request.POST.getlist('stage_name')
		descriptions = request.POST.getlist('item_description')
		prices = request.POST.getlist('unit_price')
		hours_list = request.POST.getlist('stage_hours')
		rates_list = request.POST.getlist('stage_rate')

		total = Decimal('0')
		created_items = 0
		for index, stage in enumerate(stages):
			if not stage.strip():
				continue
			# Если указаны часы и ставка — используем их
			hours_val = Decimal(hours_list[index]) if index < len(hours_list) and hours_list[index] else Decimal('1')
			rate_val = Decimal(rates_list[index]) if index < len(rates_list) and rates_list[index] else Decimal('0')
			# unit_price из формы = итого (часы × ставка), для ProposalItem: quantity=часы, unit_price=ставка
			item = ProposalItem.objects.create(
				proposal=proposal,
				stage_name=stage.strip(),
				description=(descriptions[index] if index < len(descriptions) else '').strip(),
				quantity=hours_val,
				unit_price=rate_val,
				order=index + 1,
			)
			total += item.total_price
			created_items += 1

		# Если пользователь ничего не добавил вручную — подставляем автооценку (часы/ставка/итого)
		if created_items == 0:
			auto_stages, _auto_total = estimate_stages(service_request)
			for idx, stage in enumerate(auto_stages):
				hours_val = Decimal(str(stage.get('hours', 1) or 1))
				rate_val = Decimal(str(stage.get('unit_price', 0) or 0))
				item = ProposalItem.objects.create(
					proposal=proposal,
					stage_name=stage.get('name', f'Этап {idx + 1}'),
					description=stage.get('description', ''),
					quantity=hours_val,
					unit_price=rate_val,
					order=idx + 1,
				)
				total += item.total_price

		proposal.total_amount = total
		proposal.save(update_fields=['total_amount', 'updated_at'])

		# Проверяем превышение бюджета клиента
		if service_request.budget_to and total > service_request.budget_to:
			messages.warning(
				request,
				f'Внимание: итого КП ({total:,.0f} ₽) превышает бюджет клиента ({service_request.budget_to:,.0f} ₽). '
				f'Рекомендуется скорректировать этапы.'
			)

		service_request.status = 'PROPOSAL_DRAFT'
		service_request.save(update_fields=['status', 'updated_at'])

		messages.success(request, 'Коммерческое предложение сформировано')
		return redirect('proposals:detail', pk=proposal.pk)

	# GET: автоматически подбираем этапы из шаблона
	auto_stages, auto_total = estimate_stages(service_request)

	# Адаптируем под бюджет клиента
	savings_pct = 0
	if service_request.budget_to:
		auto_stages, auto_total, savings_pct = adapt_to_budget(
			auto_stages, auto_total,
			service_request.budget_from, service_request.budget_to,
		)

	return render(request, 'proposals/create.html', {
		'request_obj': service_request,
		'auto_stages': auto_stages,
		'auto_total': auto_total,
		'savings_pct': savings_pct,
	})
