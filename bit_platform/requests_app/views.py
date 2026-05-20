from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import JsonResponse
from django.utils import timezone

from .models import ServiceRequest, RequestComment, RequestApproval
from .forms import (
    ServiceRequestForm,
    RequestCommentForm,
    RequestStatusForm,
    RequestAssignmentForm,
)
from accounts.decorators import analyst_required
from notifications.views import create_notification
from core.pipeline import (
    qualify_request,
    request_clarification,
    estimate_stages,
    adapt_to_budget,
    suggest_team_for_request,
)


@login_required
def my_requests(request):
    """Список заявок клиента"""
    requests_list = ServiceRequest.objects.filter(client=request.user).order_by('-created_at')
    
    # Фильтрация по статусу
    status = request.GET.get('status')
    if status:
        requests_list = requests_list.filter(status=status)
    
    paginator = Paginator(requests_list, 10)
    page = request.GET.get('page')
    requests_page = paginator.get_page(page)
    
    return render(request, 'requests_app/my_requests.html', {
        'requests': requests_page,
        'statuses': ServiceRequest.STATUS_CHOICES,
        'current_status': status,
    })


@login_required
def create_request(request):
    """Создание новой заявки"""
    from clients.models import ClientCompany

    client_company = ClientCompany.objects.filter(owner=request.user).first()
    required_requisites = [
        'short_name', 'inn', 'ogrn', 'legal_address',
        'bank_name', 'bik', 'settlement_account',
    ]
    missing = []
    if not client_company:
        missing = ['карточка компании']
    else:
        label_map = {
            'short_name': 'краткое наименование',
            'inn': 'ИНН',
            'ogrn': 'ОГРН',
            'legal_address': 'юридический адрес',
            'bank_name': 'наименование банка',
            'bik': 'БИК',
            'settlement_account': 'расчётный счёт',
        }
        for field in required_requisites:
            if not getattr(client_company, field, None):
                missing.append(label_map[field])

    if missing:
        messages.error(
            request,
            'Перед созданием заявки заполните реквизиты компании: ' + ', '.join(missing)
        )
        return redirect('clients:my_company')

    if request.method == 'POST':
        form = ServiceRequestForm(request.POST, request.FILES)
        form.fields['company_name'].widget.attrs['readonly'] = True
        if form.is_valid():
            service_request = form.save(commit=False)
            service_request.client = request.user
            
            # Привязываем компанию клиента, если есть
            if client_company:
                service_request.client_company = client_company
                service_request.company_name = client_company.short_name

            # Заполняем контактные данные из профиля, если не указаны
            if not service_request.contact_email:
                service_request.contact_email = request.user.email
            if not service_request.contact_phone and hasattr(request.user, 'profile'):
                service_request.contact_phone = request.user.profile.phone
            if not service_request.company_name and hasattr(request.user, 'profile'):
                service_request.company_name = request.user.profile.company
            
            service_request.save()

            # ── Сохраняем вложения ──
            from requests_app.models import RequestAttachment
            for f in request.FILES.getlist('attachments'):
                RequestAttachment.objects.create(
                    request=service_request,
                    file=f,
                    filename=f.name,
                    uploaded_by=request.user,
                )

            # ── Этап 1: квалификация ──
            is_valid, issues = qualify_request(service_request)
            if not is_valid:
                for issue in issues:
                    messages.warning(request, f'⚠ {issue}')

            service_request.run_auto_triage()
            service_request.apply_routing_rules()
            if not service_request.analyst:
                team_suggestion = suggest_team_for_request(service_request)
                analysts = team_suggestion.get('recommended_analysts', []) if isinstance(team_suggestion, dict) else []
                if analysts:
                    service_request.analyst = analysts[0]
            service_request.executor = None
            service_request.save(update_fields=[
                'budget_from', 'budget_to', 'deadline', 'sla_due_at',
                'automation_recommendation', 'analyst', 'executor', 'updated_at',
            ])
            service_request.ensure_approval_workflow()
            service_request.auto_assign_approval_owners()

            if service_request.analyst:
                create_notification(
                    recipient=service_request.analyst,
                    title='Новая заявка назначена автоматически',
                    message=f'{service_request.number}: {service_request.title[:80]}',
                    notification_type='request',
                    sender=request.user,
                    link=f'/requests/{service_request.pk}/',
                )

            if is_valid:
                messages.success(request, f'Заявка {service_request.number} создана.')
            else:
                messages.info(request, f'Заявка {service_request.number} создана, но есть замечания — аналитик запросит уточнения.')
            return redirect('requests_app:request_detail', pk=service_request.pk)
    else:
        # Предзаполняем данные из профиля
        initial = {}
        if client_company:
            initial['company_name'] = client_company.short_name
        if hasattr(request.user, 'profile'):
            initial['contact_phone'] = request.user.profile.phone
            if not initial.get('company_name'):
                initial['company_name'] = request.user.profile.company
        initial['contact_email'] = request.user.email
        form = ServiceRequestForm(initial=initial)
        form.fields['company_name'].widget.attrs['readonly'] = True
    
    return render(request, 'requests_app/create_request.html', {'form': form})


@login_required
def edit_request(request, pk):
    """Редактирование заявки клиентом (пока аналитик не начал работу)."""
    service_request = get_object_or_404(ServiceRequest, pk=pk)

    # Только клиент-владелец может редактировать
    if service_request.client != request.user:
        messages.error(request, 'Только автор заявки может её редактировать')
        return redirect('requests_app:request_detail', pk=pk)

    # Разрешаем редактирование только на ранних статусах
    editable_statuses = {'IN_ANALYSIS', 'ESTIMATION'}
    if service_request.status not in editable_statuses:
        messages.error(request, 'Заявку нельзя редактировать на текущем этапе')
        return redirect('requests_app:request_detail', pk=pk)

    existing_attachments = service_request.attachments.all()

    if request.method == 'POST':
        form = ServiceRequestForm(request.POST, request.FILES, instance=service_request)
        if form.is_valid():
            form.save()

            # Удаление выбранных вложений
            delete_ids = request.POST.getlist('delete_attachment')
            if delete_ids:
                service_request.attachments.filter(pk__in=delete_ids).delete()

            # Добавление новых вложений
            from requests_app.models import RequestAttachment
            for f in request.FILES.getlist('attachments'):
                RequestAttachment.objects.create(
                    request=service_request,
                    file=f,
                    filename=f.name,
                    uploaded_by=request.user,
                )

            messages.success(request, 'Заявка обновлена')
            return redirect('requests_app:request_detail', pk=pk)
    else:
        form = ServiceRequestForm(instance=service_request)

    return render(request, 'requests_app/edit_request.html', {
        'form': form,
        'request_obj': service_request,
        'existing_attachments': existing_attachments,
    })


@login_required
def request_detail(request, pk):
    """Детальная страница заявки"""
    service_request = get_object_or_404(ServiceRequest, pk=pk)
    
    # Проверка доступа
    user = request.user
    profile = getattr(user, 'profile', None)

    role = profile.role if profile else None
    is_admin = role == 'admin'
    
    can_view = (
        service_request.client == user or
        service_request.analyst == user or
        service_request.executor == user or
        (profile and profile.role in ['analyst', 'admin'])
    )
    
    if not can_view:
        messages.error(request, 'У вас нет доступа к этой заявке')
        return redirect('accounts:dashboard')
    
    # Определяем права на редактирование
    can_change_status = (
        is_admin
        or service_request.analyst == user
        or service_request.executor == user
        or service_request.client == user
    )
    can_assign = is_admin
    approvals = service_request.approvals.select_related('assigned_to', 'decided_by')
    
    # Обработка форм
    comment_form = RequestCommentForm()
    status_form = RequestStatusForm(instance=service_request, user=user) if can_change_status else None
    assignment_form = RequestAssignmentForm(instance=service_request) if can_assign else None
    
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'comment':
            comment_form = RequestCommentForm(request.POST)
            if comment_form.is_valid():
                comment = comment_form.save(commit=False)
                comment.request = service_request
                comment.author = user
                comment.save()
                # Уведомляем аналитика о комментарии клиента
                if role == 'client' and service_request.analyst:
                    create_notification(
                        recipient=service_request.analyst,
                        title='Новый комментарий клиента',
                        message=f'Клиент {user.get_full_name()} оставил комментарий к заявке {service_request.number}',
                        notification_type='request',
                        sender=user,
                        link=f'/requests/{service_request.pk}/',
                    )
                messages.success(request, 'Комментарий добавлен')
                return redirect('requests_app:request_detail', pk=pk)
        
        elif action == 'status' and can_change_status:
            status_form = RequestStatusForm(request.POST, instance=service_request, user=user)
            if status_form.is_valid():
                new_status = status_form.cleaned_data['status']
                status_comment = status_form.cleaned_data.get('status_comment', '')
                try:
                    service_request.change_status(new_status, user, status_comment)
                    messages.success(request, 'Статус обновлён')
                except ValueError as exc:
                    messages.error(request, str(exc))
                return redirect('requests_app:request_detail', pk=pk)

        elif action == 'assign' and can_assign:
            assignment_form = RequestAssignmentForm(request.POST, instance=service_request)
            if assignment_form.is_valid():
                assignment_form.save()
                service_request.ensure_approval_workflow()
                service_request.auto_assign_approval_owners()

                if service_request.analyst:
                    create_notification(
                        recipient=service_request.analyst,
                        title='Назначена заявка',
                        message=f'{service_request.number}: вы назначены аналитиком',
                        notification_type='request',
                        sender=user,
                        link=f'/requests/{service_request.pk}/',
                    )
                if service_request.executor:
                    create_notification(
                        recipient=service_request.executor,
                        title='Назначена заявка',
                        message=f'{service_request.number}: вы назначены исполнителем',
                        notification_type='request',
                        sender=user,
                        link=f'/requests/{service_request.pk}/',
                    )

                messages.success(request, 'Ответственные назначены по правилам доступа')
                return redirect('requests_app:request_detail', pk=pk)

        elif action == 'assign':
            messages.error(request, 'Недостаточно прав для назначения ответственных')
            return redirect('requests_app:request_detail', pk=pk)

        elif action == 'client_cancel' and service_request.client == user:
            terminal = {'COMPLETED', 'CANCELLED', 'REJECTED', 'ARCHIVED'}
            # Запрещаем отмену, если КП уже принято клиентом
            has_accepted_proposal = service_request.proposals.filter(status='accepted').exists()
            if has_accepted_proposal:
                messages.error(request, 'Невозможно отменить заявку: коммерческое предложение уже принято')
                return redirect('requests_app:request_detail', pk=pk)
            if service_request.status not in terminal:
                try:
                    service_request.change_status('CANCELLED', user, 'Отменено клиентом', force=True)
                    # Уведомляем аналитика об отмене
                    if service_request.analyst:
                        create_notification(
                            recipient=service_request.analyst,
                            title='Заявка отменена клиентом',
                            message=f'Клиент {user.get_full_name()} отменил заявку {service_request.number}',
                            notification_type='request',
                            sender=user,
                            link=f'/requests/{service_request.pk}/',
                        )
                    messages.success(request, 'Заявка отменена')
                except ValueError as exc:
                    messages.error(request, str(exc))
            else:
                messages.error(request, 'Невозможно отменить заявку в текущем статусе')
            return redirect('requests_app:request_detail', pk=pk)

        elif action == 'clarification' and (is_admin or service_request.analyst == user):
            questions = request.POST.get('clarification_text', '').strip()
            if questions:
                request_clarification(service_request, user, questions)
                messages.success(request, 'Запрос уточнений отправлен клиенту')
            else:
                messages.error(request, 'Введите текст вопросов')
            return redirect('requests_app:request_detail', pk=pk)

        elif action == 'approval_decision' and can_change_status:
            approval_id = request.POST.get('approval_id')
            decision = request.POST.get('decision')
            comment = request.POST.get('approval_comment', '').strip()
            approval = get_object_or_404(RequestApproval, pk=approval_id, request=service_request)

            if decision not in ['approved', 'rejected', 'rework']:
                messages.error(request, 'Некорректное решение по этапу')
                return redirect('requests_app:request_detail', pk=pk)

            approval.status = decision
            approval.comment = comment
            approval.decided_by = user
            approval.decided_at = timezone.now()
            approval.save()

            if decision == 'approved':
                next_step = service_request.approvals.filter(order__gt=approval.order, status='pending').order_by('order').first()
                if next_step and not next_step.assigned_to:
                    next_step.assigned_to = user
                    next_step.save()

                has_pending = service_request.approvals.filter(status='pending').exists()
                if not has_pending and service_request.status in ['IN_ANALYSIS', 'ESTIMATION', 'PROPOSAL_DRAFT', 'PROPOSAL_SENT', 'CLIENT_REVIEW', 'NEGOTIATION']:
                    service_request.status = 'CONTRACT_DRAFT'
                    service_request.save(update_fields=['status', 'updated_at'])
            else:
                service_request.status = 'IN_ANALYSIS'
                service_request.save(update_fields=['status', 'updated_at'])

            create_notification(
                recipient=service_request.client,
                title='Обновлён этап согласования заявки',
                message=f'Заявка #{service_request.pk}: этап "{approval.title}" — {approval.get_status_display()}',
                notification_type='request',
                sender=user,
                link=f'/requests/{service_request.pk}/',
            )

            messages.success(request, 'Этап согласования обновлён')
            return redirect('requests_app:request_detail', pk=pk)
    
    # Комментарии (для клиента скрываем внутренние)
    comments = service_request.comments.all()
    if profile and profile.role == 'client':
        comments = comments.filter(is_internal=False)

    # Автосинхронизация: если все связанные проекты уже в архиве,
    # переводим заявку в ARCHIVED, чтобы пайплайн доходил до финального этапа.
    if service_request.status != 'ARCHIVED':
        has_archived_projects = service_request.projects.filter(status='archived').exists()
        has_not_archived_projects = service_request.projects.exclude(status='archived').exists()
        if has_archived_projects and not has_not_archived_projects:
            try:
                service_request.change_status('ARCHIVED', user, 'Автосинхронизация: все проекты в архиве', force=True)
            except Exception:
                service_request.status = 'ARCHIVED'
                service_request.completed_at = service_request.completed_at or timezone.now()
                service_request.save(update_fields=['status', 'completed_at', 'updated_at'])

    # История статусов
    status_history = service_request.status_history.select_related('changed_by').all()

    # Пайплайн-стадии для визуализации
    PIPELINE_SEQUENCE = [
        ('IN_ANALYSIS', 'Анализ'),
        ('ESTIMATION', 'Оценка'),
        ('PROPOSAL_DRAFT', 'КП'),
        ('PROPOSAL_SENT', 'КП отпр.'),
        ('CLIENT_REVIEW', 'Обзор'),
        ('NEGOTIATION', 'Переговоры'),
        ('CLIENT_APPROVED', 'Одобрен'),
        ('INTERNAL_APPROVAL', 'Вн. согл.'),
        ('FINANCIAL_CHECK', 'Финансы'),
        ('CONTRACT_DRAFT', 'Договор'),
        ('CONTRACT_SENT', 'Дог. отпр.'),
        ('CONTRACT_SIGNED', 'Подписан'),
        ('ADVANCE_PAYMENT', 'Аванс'),
        ('CONVERTED', 'Проект'),
        ('IN_PROGRESS', 'Работа'),
        ('ARCHIVED', 'Архив'),
    ]

    # Для визуального пайплайна считаем COMPLETED как промежуточное состояние перед архивом.
    pipeline_status = service_request.status
    if pipeline_status == 'COMPLETED':
        pipeline_status = 'IN_PROGRESS'

    current_idx = None
    for i, (code, _) in enumerate(PIPELINE_SEQUENCE):
        if code == pipeline_status:
            current_idx = i
            break
    pipeline_stages = []
    for i, (code, label) in enumerate(PIPELINE_SEQUENCE):
        passed = current_idx is not None and i < current_idx
        is_current = code == pipeline_status
        pipeline_stages.append({'code': code, 'label': label, 'passed': passed, 'is_current': is_current})

    # Процент выполнения пайплайна (для визуальной линии прогресса)
    pipeline_progress_pct = 0
    if current_idx is not None and len(PIPELINE_SEQUENCE) > 1:
        pipeline_progress_pct = int((current_idx / (len(PIPELINE_SEQUENCE) - 1)) * 100)

    # ── Данные пайплайна для аналитика ──
    qualification_valid, qualification_issues = qualify_request(service_request)
    stages_estimate, estimate_total = estimate_stages(service_request)

    # Скрываем пройденные этапы
    _stage1_statuses = {'IN_ANALYSIS', 'ESTIMATION'}
    _stage2_statuses = {'IN_ANALYSIS', 'ESTIMATION', 'PROPOSAL_DRAFT', 'PROPOSAL_SENT', 'CLIENT_REVIEW', 'NEGOTIATION'}
    show_stage1 = service_request.status in _stage1_statuses
    show_stage2 = service_request.status in _stage2_statuses

    # Адаптируем под бюджет клиента
    savings_pct = 0
    if service_request.budget_to:
        stages_estimate, estimate_total, savings_pct = adapt_to_budget(
            stages_estimate, estimate_total,
            service_request.budget_from, service_request.budget_to,
        )

    # Подсказка по команде (только для ранних стадий)
    team_suggestions = None
    if service_request.status in ('IN_ANALYSIS', 'ESTIMATION', 'PROPOSAL_DRAFT'):
        try:
            team_suggestions, _ = suggest_team_for_request(service_request)
        except Exception:
            team_suggestions = None

    return render(request, 'requests_app/request_detail.html', {
        'request_obj': service_request,
        'comments': comments,
        'comment_form': comment_form,
        'status_form': status_form,
        'assignment_form': assignment_form,
        'can_edit_status': can_change_status,
        'can_assign': can_assign,
        'approvals': approvals,
        'status_history': status_history,
        'pipeline_stages': pipeline_stages,
        'pipeline_progress_pct': pipeline_progress_pct,
        # Пайплайн-данные
        'qualification_valid': qualification_valid,
        'qualification_issues': qualification_issues,
        'stages_estimate': stages_estimate,
        'estimate_total': estimate_total,
        'savings_pct': savings_pct,
        'team_suggestions': team_suggestions,
        'show_stage1': show_stage1,
        'show_stage2': show_stage2,
        # Связанные объекты
        'related_proposals': service_request.proposals.all().order_by('-created_at'),
        'related_contracts': service_request.contracts.all().order_by('-created_at'),
        'related_documents': service_request.business_documents.all().order_by('-created_at'),
        'related_projects': service_request.projects.all().order_by('-created_at'),
        'related_tasks': service_request.tasks.select_related('assignee').all().order_by('-created_at')[:5],
        # Флаг для блокировки отмены
        'has_accepted_proposal': service_request.proposals.filter(status='accepted').exists(),
    })

# === Представления для аналитика ===

@login_required
@analyst_required
def all_requests(request):
    """Все заявки (для аналитика)"""
    requests_list = ServiceRequest.objects.all().order_by('-created_at')
    
    # Фильтрация
    status = request.GET.get('status')
    service_type = request.GET.get('service_type')
    search = request.GET.get('search')
    
    if status:
        requests_list = requests_list.filter(status=status)
    if service_type:
        requests_list = requests_list.filter(service_type=service_type)
    if search:
        requests_list = requests_list.filter(
            Q(title__icontains=search) |
            Q(description__icontains=search) |
            Q(company_name__icontains=search)
        )
    
    paginator = Paginator(requests_list, 15)
    page = request.GET.get('page')
    requests_page = paginator.get_page(page)

    status_filter_choices = [
        ('IN_ANALYSIS', 'Анализ'),
        ('ESTIMATION', 'Оценка'),
        ('PROPOSAL_DRAFT', 'КП'),
        ('PROPOSAL_SENT', 'КП отпр.'),
        ('NEGOTIATION', 'Переговоры'),
        ('CONTRACT_DRAFT', 'Договор'),
        ('CONTRACT_SENT', 'Дог. отпр.'),
        ('CONTRACT_SIGNED', 'Подписан'),
        ('ADVANCE_PAYMENT', 'Аванс'),
        ('CONVERTED', 'Проект'),
        ('IN_PROGRESS', 'Работа'),
        ('ARCHIVED', 'Архив'),
    ]
    
    return render(request, 'requests_app/all_requests.html', {
        'requests': requests_page,
        'statuses': status_filter_choices,
        'service_types': ServiceRequest.SERVICE_CHOICES,
        'current_status': status,
        'current_service_type': service_type,
        'search': search,
    })


@login_required
@analyst_required
def new_requests(request):
    """Новые заявки (для аналитика)"""
    early_statuses = ['IN_ANALYSIS', 'ESTIMATION', 'PROPOSAL_DRAFT']
    requests_list = ServiceRequest.objects.filter(status__in=early_statuses).order_by('-created_at')
    
    paginator = Paginator(requests_list, 15)
    page = request.GET.get('page')
    requests_page = paginator.get_page(page)
    
    return render(request, 'requests_app/new_requests.html', {
        'requests': requests_page,
    })


@login_required
@analyst_required
def my_analysis(request):
    """Заявки аналитика"""
    requests_list = ServiceRequest.objects.filter(analyst=request.user).order_by('-created_at')
    
    status = request.GET.get('status')
    if status:
        requests_list = requests_list.filter(status=status)
    
    paginator = Paginator(requests_list, 15)
    page = request.GET.get('page')
    requests_page = paginator.get_page(page)
    
    return render(request, 'requests_app/my_analysis.html', {
        'requests': requests_page,
        'statuses': ServiceRequest.STATUS_CHOICES,
        'current_status': status,
    })
