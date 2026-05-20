from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib import messages
from django.core.paginator import Paginator
from django.utils import timezone
from django.db import models

from accounts.decorators import analyst_required
from core.pipeline import get_executor_workload, find_executors_for_skills
from notifications.views import create_notification
from .models import Task, TaskAssignment


@login_required
def my_tasks(request):
    """Мои задачи"""
    profile = getattr(request.user, 'profile', None)
    role = getattr(profile, 'role', None)

    # Аналитик/админ видят задачи по своим проектам + назначенные
    if role in ['analyst', 'admin']:
        tasks_list = Task.objects.select_related('project', 'assignee').filter(
            models.Q(assignee=request.user) |
            models.Q(project__manager=request.user) |
            models.Q(created_by=request.user)
        ).distinct().order_by('-created_at')
    else:
        tasks_list = Task.objects.select_related('project', 'assignee').filter(
            models.Q(assignee=request.user) | models.Q(assignments__assignee=request.user)
        ).distinct().order_by('-created_at')

    # Фильтрация
    status = request.GET.get('status')
    priority = request.GET.get('priority')

    if status:
        tasks_list = tasks_list.filter(status=status)
    if priority:
        tasks_list = tasks_list.filter(priority=priority)

    paginator = Paginator(tasks_list, 15)
    page = request.GET.get('page')
    tasks_page = paginator.get_page(page)

    return render(request, 'tasks/my_tasks.html', {
        'tasks': tasks_page,
        'statuses': Task.STATUS_CHOICES,
        'priorities': Task.PRIORITY_CHOICES,
        'current_status': status,
        'current_priority': priority,
    })


@login_required
@analyst_required
def all_tasks(request):
    """Все задачи (для аналитика/диспетчера)"""
    tasks_list = Task.objects.select_related('project', 'assignee', 'created_by').order_by('-created_at')

    status = request.GET.get('status')
    priority = request.GET.get('priority')
    unassigned = request.GET.get('unassigned')
    overdue = request.GET.get('overdue')
    today = timezone.now().date()

    if status:
        tasks_list = tasks_list.filter(status=status)
    if priority:
        tasks_list = tasks_list.filter(priority=priority)
    if unassigned:
        tasks_list = tasks_list.filter(assignee__isnull=True)
    if overdue:
        tasks_list = tasks_list.filter(due_date__lt=today).exclude(status='done')

    paginator = Paginator(tasks_list, 20)
    page = request.GET.get('page')
    tasks_page = paginator.get_page(page)

    # Исполнители для назначения
    executors = User.objects.filter(profile__role='executor').order_by('first_name', 'last_name')

    return render(request, 'tasks/all_tasks.html', {
        'tasks': tasks_page,
        'statuses': Task.STATUS_CHOICES,
        'priorities': Task.PRIORITY_CHOICES,
        'current_status': status,
        'current_priority': priority,
        'unassigned': unassigned,
        'overdue': overdue,
        'executors': executors,
    })


@login_required
def task_detail(request, pk):
    """Детальная страница задачи"""
    task = get_object_or_404(Task.objects.select_related('project', 'assignee', 'created_by', 'service_request'), pk=pk)

    user = request.user
    profile = getattr(user, 'profile', None)
    role = getattr(profile, 'role', None)

    # Проверка доступа — аналитик и админ могут видеть все
    can_view = (
        role in ['analyst', 'admin'] or
        task.assignee == user or
        task.created_by == user or
        task.assignments.filter(assignee=user).exists() or
        user in task.project.team.all() or
        task.project.manager == user
    )

    if not can_view:
        messages.error(request, 'У вас нет доступа к этой задаче')
        return redirect('accounts:dashboard')

    # Аналитик/менеджер проекта может назначать и менять статусы
    is_manager = (
        role in ['analyst', 'admin'] or
        task.project.manager == user or
        task.created_by == user
    )

    if request.method == 'POST':
        action = request.POST.get('action')

        # Изменение статуса задачи
        if action == 'task_status' and (task.assignee == user or is_manager):
            new_status = request.POST.get('status')
            if new_status in dict(Task.STATUS_CHOICES):
                task.status = new_status
                if new_status == 'done':
                    task.completed_at = timezone.now()
                task.save()

                # Если задача завершена — проверяем, все ли задачи проекта выполнены
                if new_status == 'done':
                    _check_all_tasks_done(task.project, user)

                messages.success(request, 'Статус задачи обновлён')
                return redirect('tasks:task_detail', pk=pk)

        # Назначение исполнителя на задачу (аналитик/менеджер)
        elif action == 'assign_executor' and is_manager:
            executor_id = request.POST.get('executor_id')
            if executor_id:
                executor = get_object_or_404(User, pk=executor_id)
                task.assignee = executor
                task.save(update_fields=['assignee', 'updated_at'])
                # Добавляем исполнителя в команду проекта
                task.project.team.add(executor)
                create_notification(
                    recipient=executor,
                    title='Назначена задача',
                    message=f'Вам назначена задача: {task.title}',
                    notification_type='request',
                    sender=user,
                    link=f'/tasks/{task.pk}/',
                )
                messages.success(request, f'Исполнитель назначен: {executor.get_full_name() or executor.username}')
            return redirect('tasks:task_detail', pk=pk)

        # Назначение исполнителя на этап
        elif action == 'assign_stage_executor' and is_manager:
            assignment_id = request.POST.get('assignment_id')
            executor_id = request.POST.get('executor_id')
            assignment = get_object_or_404(TaskAssignment, pk=assignment_id, task=task)
            if executor_id:
                executor = get_object_or_404(User, pk=executor_id)
                assignment.assignee = executor
                assignment.save(update_fields=['assignee', 'updated_at'])
                # Синхронизируем task.assignee — ставим назначенного исполнителя,
                # если задача ещё не имеет исполнителя, либо это единственный этап
                if not task.assignee or task.assignments.count() == 1:
                    task.assignee = executor
                    task.save(update_fields=['assignee', 'updated_at'])
                task.project.team.add(executor)
                create_notification(
                    recipient=executor,
                    title='Назначен этап задачи',
                    message=f'Вам назначен этап «{assignment.get_stage_display()}» в задаче: {task.title}',
                    notification_type='request',
                    sender=user,
                    link=f'/tasks/{task.pk}/',
                )
                messages.success(request, f'Этап «{assignment.get_stage_display()}» назначен: {executor.get_full_name() or executor.username}')
            return redirect('tasks:task_detail', pk=pk)

        # Изменение статуса этапа
        elif action == 'assignment_status':
            assignment_id = request.POST.get('assignment_id')
            assignment = get_object_or_404(TaskAssignment, pk=assignment_id, task=task)
            if assignment.assignee != user and not is_manager:
                messages.error(request, 'Недостаточно прав для изменения этапа')
                return redirect('tasks:task_detail', pk=pk)

            new_status = request.POST.get('assignment_status')
            if new_status in dict(TaskAssignment.STATUS_CHOICES):
                assignment.status = new_status
                if new_status == 'in_progress' and not assignment.actual_start:
                    assignment.actual_start = timezone.now().date()
                if new_status == 'done' and not assignment.actual_end:
                    assignment.actual_end = timezone.now().date()
                assignment.save()

                if not task.assignments.exclude(status='done').exists():
                    task.status = 'done'
                    task.completed_at = timezone.now()
                    task.save(update_fields=['status', 'completed_at', 'updated_at'])
                    # Проверяем, все ли задачи проекта завершены
                    _check_all_tasks_done(task.project, user)
                elif task.status in ['backlog', 'todo']:
                    task.status = 'in_progress'
                    task.save(update_fields=['status', 'updated_at'])

                messages.success(request, 'Статус этапа обновлён')
                return redirect('tasks:task_detail', pk=pk)

        # Аналитик отправляет задачу на доработку
        elif action == 'send_rework' and is_manager:
            # Возврат на доработку возможен только после отправки отчёта исполнителем
            has_submitted_report = task.work_reports.exclude(status='draft').exists()
            if not has_submitted_report:
                messages.error(request, 'Сначала исполнитель должен отправить отчёт о проделанной работе')
                return redirect('tasks:task_detail', pk=pk)

            comment_text = request.POST.get('rework_comment', '').strip()
            task.status = 'in_progress'
            task.completed_at = None
            task.save(update_fields=['status', 'completed_at', 'updated_at'])
            # Сбрасываем этапы в todo
            task.assignments.filter(status='done').update(status='todo', actual_end=None)
            if task.assignee:
                create_notification(
                    recipient=task.assignee,
                    title='Задача возвращена на доработку',
                    message=f'Задача «{task.title}» возвращена на доработку. {comment_text}',
                    notification_type='request',
                    sender=user,
                    link=f'/tasks/{task.pk}/',
                )
            messages.warning(request, 'Задача отправлена на доработку')
            return redirect('tasks:task_detail', pk=pk)

        # Аналитик принимает задачу (подтверждает done)
        elif action == 'accept_task' and is_manager:
            # Принятие задачи возможно только после отправки отчёта исполнителем
            has_submitted_report = task.work_reports.exclude(status='draft').exists()
            if not has_submitted_report:
                messages.error(request, 'Нельзя принять задачу без отчёта исполнителя')
                return redirect('tasks:task_detail', pk=pk)

            task.status = 'done'
            if not task.completed_at:
                task.completed_at = timezone.now()
            task.save(update_fields=['status', 'completed_at', 'updated_at'])
            if task.assignee:
                create_notification(
                    recipient=task.assignee,
                    title='Задача принята',
                    message=f'Задача «{task.title}» принята аналитиком',
                    notification_type='request',
                    sender=user,
                    link=f'/tasks/{task.pk}/',
                )
            _check_all_tasks_done(task.project, user)
            messages.success(request, 'Задача принята')
            return redirect('tasks:task_detail', pk=pk)

    assignments = task.assignments.select_related('assignee').order_by('order', 'id')

    # Обогащаем список исполнителей: должность + загрузка
    executor_qs = User.objects.filter(profile__role='executor').select_related('profile').order_by('first_name', 'last_name')
    executors_enriched = []

    # Определяем тип этапа для рекомендации
    task_stage_type = None
    _TYPE_KEYWORDS = {
        'analysis': ['анализ', 'обследование', 'аудит', 'сбор требований', 'проектирование'],
        'backend': ['backend', 'серверн', 'бэкенд', 'устранение уязвимостей', 'конфигурация'],
        'frontend': ['frontend', 'интерфейс', 'фронтенд', 'вёрстка'],
        'integration': ['интеграция', 'обмен данными'],
        'testing': ['тестирование', 'qa', 'пентест', 'приёмка'],
        'deploy': ['внедрение', 'развёрт', 'миграция', 'монтаж', 'настройка'],
        'training': ['обучение', 'семинар'],
        'support': ['поддержка', 'мониторинг'],
        'consulting': ['консульт', 'рекоменд'],
        'security': ['безопасност', 'защит'],
    }
    title_lower = (task.title or '').lower()
    for stype, keywords in _TYPE_KEYWORDS.items():
        if any(kw in title_lower for kw in keywords):
            task_stage_type = stype
            break

    # Собираем навыки нужной категории
    from core.models import Skill, UserSkill
    relevant_skill_ids = []
    if task_stage_type:
        relevant_skill_ids = list(Skill.objects.filter(category__iexact=task_stage_type).values_list('id', flat=True))

    for ex in executor_qs:
        wl = get_executor_workload(ex)
        # Навыки исполнителя
        user_skills = list(UserSkill.objects.filter(user=ex).select_related('skill').order_by('-level'))
        skill_names = [f'{us.skill.name} ({us.get_level_display()})' for us in user_skills[:5]]
        # Совпадение с требуемыми навыками
        match_count = 0
        if relevant_skill_ids:
            match_count = sum(1 for us in user_skills if us.skill_id in relevant_skill_ids)
        executors_enriched.append({
            'user': ex,
            'position': getattr(ex.profile, 'position', '') or 'Не указана',
            'department': getattr(ex.profile, 'department', '') or '',
            'workload_hours': wl,
            'workload_pct': min(int(wl / 120 * 100), 100) if wl else 0,
            'is_overloaded': wl >= 120,
            'skills': ', '.join(skill_names) if skill_names else 'Не указаны',
            'match_count': match_count,
            'is_recommended': match_count > 0 and wl < 120,
        })

    # Определяем рекомендуемого исполнителя для задачи
    recommended_executor_id = None
    if is_manager and not task.assignee:
        try:
            from core.pipeline import _pick_assignee
            from proposals.models import ProposalItem
            # Ищем позицию КП по имени задачи
            sr = task.service_request or (task.project.service_request if task.project else None)
            if sr:
                proposal_item = ProposalItem.objects.filter(
                    proposal__request=sr,
                    stage_name=task.title,
                ).first()
                if proposal_item:
                    recommended = _pick_assignee(sr, proposal_item)
                    if recommended:
                        recommended_executor_id = recommended.pk
        except Exception:
            pass

    # Определяем, все ли этапы/задача в статусе "на проверке" (review) или done
    needs_review = task.status == 'review' or (
        task.status == 'done' and is_manager
    )

    can_work_on_task = (
        task.assignee == user
        or task.assignments.filter(assignee=user).exists()
        or is_manager
    )

    can_track_time_report = (
        role == 'executor' and (
            task.assignee == user
            or task.assignments.filter(assignee=user).exists()
        )
    )

    review_reports = task.work_reports.exclude(status='draft').order_by('-created_at')

    return render(request, 'tasks/task_detail.html', {
        'task': task,
        'statuses': Task.STATUS_CHOICES,
        'assignments': assignments,
        'assignment_statuses': TaskAssignment.STATUS_CHOICES,
        'is_manager': is_manager,
        'executors': executor_qs,
        'executors_enriched': executors_enriched,
        'recommended_executor_id': recommended_executor_id,
        'needs_review': needs_review,
        'task_stage_type': task_stage_type or '',
        'can_work_on_task': can_work_on_task,
        'can_track_time_report': can_track_time_report,
        'review_reports': review_reports,
    })


def _check_all_tasks_done(project, actor):
    """Если все задачи проекта завершены — уведомляем аналитика для проверки."""
    all_done = not project.tasks.exclude(status='done').exists()
    total = project.tasks.count()
    if not total:
        return

    # Обновляем прогресс проекта
    done_count = project.tasks.filter(status='done').count()
    project.progress = int(done_count / total * 100)
    project.save(update_fields=['progress', 'updated_at'])

    if all_done and project.status != 'completed':
        manager = project.manager
        if manager:
            create_notification(
                recipient=manager,
                title='Все задачи выполнены — проверьте проект',
                message=f'Все {total} задач(и) проекта «{project.name}» выполнены. Проверьте результаты и завершите проект.',
                notification_type='request',
                sender=actor,
                link=f'/projects/{project.pk}/',
            )
