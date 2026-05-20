from decimal import Decimal
from datetime import timedelta
import uuid

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db import models
from django.utils import timezone

from notifications.views import create_notification
from .models import Project


def _get_closing_docs_state(project):
    """Возвращает состояние закрывающих документов для архивации."""
    sr = project.service_request
    if not sr:
        return {
            'has_sr': False,
            'act': None,
            'invoice': None,
            'act_ok': True,
            'invoice_ok': True,
            'ready_for_archive': True,
        }

    act = sr.business_documents.filter(doc_type='act').order_by('-created_at').first()
    invoice = sr.business_documents.filter(doc_type='invoice').order_by('-created_at').first()

    act_ok = bool(act and act.status in ('signed', 'paid'))
    invoice_ok = bool(invoice and invoice.status == 'paid')

    return {
        'has_sr': True,
        'act': act,
        'invoice': invoice,
        'act_ok': act_ok,
        'invoice_ok': invoice_ok,
        'ready_for_archive': act_ok and invoice_ok,
    }


@login_required
def my_projects(request):
    """Мои проекты"""
    profile = getattr(request.user, 'profile', None)
    role = getattr(profile, 'role', None)

    if role in ['analyst', 'admin']:
        # Аналитик/админ видят все проекты
        projects_list = Project.objects.select_related(
            'client', 'manager', 'service_request'
        ).order_by('-created_at')
    elif role == 'client':
        projects_list = Project.objects.filter(client=request.user).order_by('-created_at')
    else:
        projects_list = Project.objects.filter(
            models.Q(team=request.user) | models.Q(manager=request.user)
        ).distinct().order_by('-created_at')

    # Фильтр по статусу
    status = request.GET.get('status')
    if status:
        projects_list = projects_list.filter(status=status)

    paginator = Paginator(projects_list, 15)
    page = request.GET.get('page')
    projects_page = paginator.get_page(page)

    is_manager = role in ['analyst', 'admin']
    
    return render(request, 'projects/my_projects.html', {
        'projects': projects_page,
        'statuses': Project.STATUS_CHOICES,
        'current_status': status,
        'is_manager': is_manager,
    })


@login_required
def project_detail(request, pk):
    """Детальная страница проекта"""
    project = get_object_or_404(Project.objects.select_related('client', 'manager', 'service_request'), pk=pk)

    user = request.user
    profile = getattr(user, 'profile', None)
    role = getattr(profile, 'role', None)

    # Аналитик/админ имеют доступ ко всем проектам
    can_view = (
        role in ['analyst', 'admin'] or
        project.client == user or
        project.manager == user or
        user in project.team.all()
    )

    if not can_view:
        messages.error(request, 'У вас нет доступа к этому проекту')
        return redirect('accounts:dashboard')

    is_manager = role in ['analyst', 'admin'] or project.manager == user

    if request.method == 'POST' and is_manager:
        action = request.POST.get('action')

        if action == 'change_status':
            new_status = request.POST.get('status')
            if project.status == 'archived':
                messages.error(request, 'Проект в архиве. Изменение статуса недоступно.')
                return redirect('projects:project_detail', pk=pk)
            if new_status == 'archived':
                messages.error(request, 'Для архивации используйте действие «Отправить в архив».')
                return redirect('projects:project_detail', pk=pk)
            if new_status in dict(Project.STATUS_CHOICES):
                project.status = new_status
                project.save(update_fields=['status', 'updated_at'])
                messages.success(request, f'Статус проекта изменён на «{project.get_status_display()}»')
                return redirect('projects:project_detail', pk=pk)

    tasks = project.tasks.select_related('assignee').order_by('status', '-created_at')

    # Статистика задач
    total_tasks = tasks.count()
    done_tasks = tasks.filter(status='done').count()
    in_progress_tasks = tasks.filter(status='in_progress').count()
    unassigned_tasks = tasks.filter(assignee__isnull=True).count()

    # Автоматический прогресс из задач
    if total_tasks > 0:
        computed_progress = int(done_tasks / total_tasks * 100)
        if project.progress != computed_progress:
            project.progress = computed_progress
            project.save(update_fields=['progress', 'updated_at'])

    # Документы по заявке (акт, счёт и т.д.)
    project_documents = []
    if project.service_request:
        from documents.models import BusinessDocument
        project_documents = BusinessDocument.objects.filter(
            request=project.service_request
        ).order_by('-created_at')

    # Можно ли завершить проект (менеджер + все задачи выполнены)
    all_tasks_done = total_tasks > 0 and done_tasks == total_tasks
    can_complete = is_manager and project.status in ('active', 'planning') and all_tasks_done

    # Можно ли отправить в архив
    closing_docs = _get_closing_docs_state(project)
    can_archive = (
        is_manager
        and project.status == 'completed'
        and closing_docs['ready_for_archive']
    )

    return render(request, 'projects/project_detail.html', {
        'project': project,
        'tasks': tasks,
        'is_manager': is_manager,
        'total_tasks': total_tasks,
        'done_tasks': done_tasks,
        'in_progress_tasks': in_progress_tasks,
        'unassigned_tasks': unassigned_tasks,
        'statuses': Project.STATUS_CHOICES,
        'project_documents': project_documents,
        'can_complete': can_complete,
        'can_archive': can_archive,
        'closing_docs': closing_docs,
    })


@login_required
def complete_project(request, pk):
    """Завершить проект и сформировать закрывающие документы (акт + счёт)."""
    project = get_object_or_404(Project.objects.select_related('service_request', 'manager'), pk=pk)

    profile = getattr(request.user, 'profile', None)
    role = getattr(profile, 'role', None)
    is_manager = role in ['analyst', 'admin'] or project.manager == request.user

    if not is_manager:
        messages.error(request, 'Только менеджер может завершить проект')
        return redirect('projects:project_detail', pk=pk)

    if request.method != 'POST':
        return redirect('projects:project_detail', pk=pk)

    # Проверяем, что все задачи завершены
    pending_tasks = project.tasks.exclude(status='done').count()
    if pending_tasks > 0:
        messages.error(request, f'Невозможно завершить проект: {pending_tasks} задач(а) ещё не выполнены')
        return redirect('projects:project_detail', pk=pk)

    # Переводим проект в статус «Завершён»
    project.status = 'completed'
    project.progress = 100
    project.end_date = project.end_date or timezone.now().date()
    project.save(update_fields=['status', 'progress', 'end_date', 'updated_at'])

    sr = project.service_request
    if not sr:
        messages.success(request, 'Проект завершён, но заявка не привязана — документы не сформированы')
        return redirect('projects:project_detail', pk=pk)

    # Формируем акт и счёт
    from documents.models import BusinessDocument, DocumentSignature
    from contracts.models import Contract

    contract = sr.contracts.order_by('-created_at').first()
    proposal = sr.proposals.order_by('-created_at').first()

    amount = Decimal('0')
    if contract:
        amount = contract.amount or Decimal('0')
    elif proposal:
        amount = proposal.total_amount or Decimal('0')
    elif sr.budget_to:
        amount = sr.budget_to

    today = timezone.now().date()

    # Проверяем, нет ли уже закрывающих документов
    existing_acts = sr.business_documents.filter(doc_type='act').count()
    existing_invoices = sr.business_documents.filter(doc_type='invoice').count()

    docs_created = []

    if existing_acts == 0:
        act = BusinessDocument(
            request=sr,
            contract=contract,
            proposal=proposal,
            doc_type='act',
            title=f'Акт выполненных работ — проект «{project.name}»',
            amount=amount,
            description=f'Акт выполненных работ по проекту «{project.name}». Все работы выполнены в полном объёме.',
            status='issued',
            issue_date=today,
            due_date=today,
            created_by=request.user,
        )
        act.save()
        docs_created.append(act.number)

        # Отправляем акт на подписание клиенту
        import uuid
        act_sig = DocumentSignature.objects.create(
            document=act,
            signer=project.client,
            status='pending',
            token=uuid.uuid4().hex,
        )
        create_notification(
            recipient=project.client,
            title='Акт выполненных работ готов к подписанию',
            message=f'По проекту «{project.name}» сформирован акт {act.number}. Подпишите его.',
            notification_type='request',
            sender=request.user,
            link=f'/documents/{act.pk}/',
        )

    if existing_invoices == 0:
        invoice = BusinessDocument(
            request=sr,
            contract=contract,
            proposal=proposal,
            doc_type='invoice',
            title=f'Счёт на оплату — проект «{project.name}»',
            amount=amount,
            description=f'Счёт на оплату по проекту «{project.name}» согласно договору.',
            status='issued',
            issue_date=today,
            due_date=today + timedelta(days=5),
            created_by=request.user,
        )
        invoice.save()
        docs_created.append(invoice.number)

        create_notification(
            recipient=project.client,
            title='Счёт на оплату',
            message=f'По проекту «{project.name}» сформирован счёт {invoice.number} на сумму {amount:,.0f} ₽.',
            notification_type='request',
            sender=request.user,
            link=f'/documents/{invoice.pk}/',
        )

    # Переводим заявку в финальный статус
    try:
        if sr.status not in ('COMPLETED', 'CLOSED', 'ARCHIVED'):
            # Если заявка ещё не в IN_PROGRESS, переводим через промежуточные статусы
            if sr.status in ('CONVERTED', 'ADVANCE_PAYMENT', 'CONTRACT_SIGNED'):
                try:
                    sr.change_status('IN_PROGRESS', request.user, f'Проект «{project.name}» выполнен')
                except (ValueError, AttributeError):
                    pass
            if sr.status == 'IN_PROGRESS':
                sr.change_status('COMPLETED', request.user, f'Проект «{project.name}» завершён')
            elif sr.status != 'COMPLETED':
                # Принудительно завершаем
                sr.status = 'COMPLETED'
                sr.completed_at = timezone.now()
                sr.save(update_fields=['status', 'completed_at', 'updated_at'])
    except (ValueError, AttributeError):
        pass

    # Уведомляем клиента
    create_notification(
        recipient=project.client,
        title='Проект завершён',
        message=f'Проект «{project.name}» успешно завершён. Закрывающие документы готовы.',
        notification_type='request',
        sender=request.user,
        link=f'/projects/{project.pk}/',
    )

    if docs_created:
        messages.success(request, f'Проект завершён! Сформированы документы: {", ".join(docs_created)}')
    else:
        messages.success(request, 'Проект завершён! Закрывающие документы уже были сформированы ранее.')

    return redirect('projects:project_detail', pk=pk)


@login_required
def archive_project(request, pk):
    """Логическое завершение: перевод завершённого проекта в архив."""
    project = get_object_or_404(Project.objects.select_related('service_request', 'manager', 'client'), pk=pk)

    profile = getattr(request.user, 'profile', None)
    role = getattr(profile, 'role', None)
    is_manager = role in ['analyst', 'admin'] or project.manager == request.user

    if not is_manager:
        messages.error(request, 'Только менеджер может отправить проект в архив')
        return redirect('projects:project_detail', pk=pk)

    if request.method != 'POST':
        return redirect('projects:project_detail', pk=pk)

    if project.status == 'archived':
        messages.info(request, 'Проект уже находится в архиве')
        return redirect('projects:project_detail', pk=pk)

    if project.status != 'completed':
        messages.error(request, 'В архив можно отправить только завершённый проект')
        return redirect('projects:project_detail', pk=pk)

    closing_docs = _get_closing_docs_state(project)
    if not closing_docs['ready_for_archive']:
        messages.error(
            request,
            'Невозможно архивировать проект: акт должен быть подписан, а счёт — оплачен.'
        )
        return redirect('projects:project_detail', pk=pk)

    project.status = 'archived'
    project.end_date = project.end_date or timezone.now().date()
    project.save(update_fields=['status', 'end_date', 'updated_at'])

    sr = project.service_request
    if sr and sr.status != 'ARCHIVED':
        try:
            # Сначала пробуем штатный переход по карте статусов
            sr.change_status('ARCHIVED', request.user, f'Проект «{project.name}» отправлен в архив')
        except (ValueError, AttributeError):
            # Фолбэк: фиксируем архивный статус принудительно
            sr.status = 'ARCHIVED'
            sr.completed_at = sr.completed_at or timezone.now()
            sr.save(update_fields=['status', 'completed_at', 'updated_at'])

    create_notification(
        recipient=project.client,
        title='Проект отправлен в архив',
        message=f'Проект «{project.name}» завершён и переведён в архив.',
        notification_type='request',
        sender=request.user,
        link=f'/projects/{project.pk}/',
    )

    messages.success(request, 'Проект успешно отправлен в архив')
    return redirect('projects:project_detail', pk=pk)
