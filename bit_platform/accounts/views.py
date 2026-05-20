from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render, get_object_or_404
from django.contrib import messages
from django.utils import timezone
from django.contrib.auth.models import User
from django.db.models import Count, Q

from .forms import UserRegisterForm, UserProfileForm, UserUpdateForm
from .models import UserProfile


def register_view(request):
    """Регистрация нового пользователя"""
    if request.user.is_authenticated:
        return redirect('accounts:profile')
    
    if request.method == 'POST':
        form = UserRegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, 'Регистрация прошла успешно! Добро пожаловать!')
            return redirect('accounts:profile')
    else:
        form = UserRegisterForm()

    return render(request, 'accounts/register.html', {'form': form})


@login_required
def profile_view(request):
    """Просмотр профиля"""
    return render(request, 'accounts/profile.html', {
        'profile': request.user.profile
    })


@login_required
def profile_edit_view(request):
    """Редактирование профиля"""
    if request.method == 'POST':
        user_form = UserUpdateForm(request.POST, instance=request.user)
        profile_form = UserProfileForm(request.POST, request.FILES, instance=request.user.profile)
        
        if user_form.is_valid() and profile_form.is_valid():
            user_form.save()
            profile_form.save()
            messages.success(request, 'Профиль успешно обновлён!')
            return redirect('accounts:profile')
    else:
        user_form = UserUpdateForm(instance=request.user)
        profile_form = UserProfileForm(instance=request.user.profile)
    
    return render(request, 'accounts/profile_edit.html', {
        'user_form': user_form,
        'profile_form': profile_form,
    })


@login_required
def dashboard_redirect(request):
    """Перенаправление в нужный личный кабинет в зависимости от роли"""
    profile = request.user.profile
    
    if profile.is_client:
        return redirect('accounts:client_dashboard')
    elif profile.is_analyst:
        return redirect('accounts:analyst_dashboard')
    elif profile.is_executor:
        return redirect('accounts:executor_dashboard')
    elif profile.is_admin:
        return redirect('admin:index')
    
    return redirect('accounts:client_dashboard')


@login_required
def client_dashboard(request):
    """Личный кабинет клиента"""
    from requests_app.models import ServiceRequest
    from documents.models import BusinessDocument
    
    requests = ServiceRequest.objects.filter(client=request.user).order_by('-created_at')
    
    terminal = ['COMPLETED', 'CANCELLED', 'REJECTED', 'ARCHIVED']

    # Документы клиента для скачивания (КП, договоры, акты, счета)
    client_documents = BusinessDocument.objects.filter(
        request__client=request.user,
        doc_type__in=['proposal', 'contract', 'act', 'invoice'],
        status__in=['issued', 'approved', 'signed'],
    ).select_related('request', 'contract', 'proposal').order_by('-created_at')[:10]

    # Документы, ожидающие подписания
    pending_signatures = BusinessDocument.objects.filter(
        request__client=request.user,
        signatures__signer=request.user,
        signatures__status='pending',
    ).distinct().select_related('request').order_by('-created_at')

    context = {
        'requests': requests[:5],
        'total_requests': requests.count(),
        'active_requests': requests.exclude(status__in=terminal).count(),
        'completed_requests': requests.filter(status='COMPLETED').count(),
        'client_documents': client_documents,
        'pending_signatures': pending_signatures,
    }
    return render(request, 'accounts/dashboards/client.html', context)


@login_required
def analyst_dashboard(request):
    """Личный кабинет аналитика с аналитическими диаграммами"""
    from requests_app.models import ServiceRequest
    from tasks.models import Task
    from projects.models import Project
    from time_tracking.models import TimeEntry
    from django.contrib.auth.models import User
    from django.db.models import Count, Sum, Q, Avg, F
    from django.db.models.functions import TruncMonth
    from datetime import timedelta
    import json

    today = timezone.now().date()
    month_start = today.replace(day=1)

    # Все заявки для аналитика
    all_requests = ServiceRequest.objects.all().order_by('-created_at')
    early = ['IN_ANALYSIS', 'ESTIMATION', 'PROPOSAL_DRAFT']
    new_requests = ServiceRequest.objects.filter(status__in=early).order_by('-created_at')

    # Задачи без исполнителя
    unassigned_tasks = Task.objects.filter(assignee__isnull=True).select_related('project').order_by('-created_at')

    # ═══ Данные для диаграмм ═══

    # 1. Заявки по статусам (Pie/Doughnut)
    status_labels = dict(ServiceRequest.STATUS_CHOICES)
    requests_by_status = list(
        ServiceRequest.objects.values('status')
        .annotate(count=Count('id'))
        .order_by('-count')
    )
    chart_status_labels = json.dumps([status_labels.get(r['status'], r['status']) for r in requests_by_status], ensure_ascii=False)
    chart_status_data = json.dumps([r['count'] for r in requests_by_status])

    # 2. Заявки по типам услуг (Bar)
    service_labels = dict(ServiceRequest.SERVICE_CHOICES)
    requests_by_service = list(
        ServiceRequest.objects.values('service_type')
        .annotate(count=Count('id'))
        .order_by('-count')
    )
    chart_service_labels = json.dumps([service_labels.get(r['service_type'], r['service_type']) for r in requests_by_service], ensure_ascii=False)
    chart_service_data = json.dumps([r['count'] for r in requests_by_service])

    # 3. Заявки по месяцам (Line) — последние 6 месяцев
    six_months_ago = today - timedelta(days=180)
    requests_by_month = list(
        ServiceRequest.objects.filter(created_at__date__gte=six_months_ago)
        .annotate(month=TruncMonth('created_at'))
        .values('month')
        .annotate(count=Count('id'))
        .order_by('month')
    )
    chart_month_labels = json.dumps([r['month'].strftime('%b %Y') for r in requests_by_month], ensure_ascii=False)
    chart_month_data = json.dumps([r['count'] for r in requests_by_month])

    # 4. Эффективность сотрудников (Bar) — задачи выполненные vs общее
    executors = (
        User.objects.filter(profile__role='executor')
        .annotate(
            total_tasks=Count('assigned_tasks'),
            done_tasks=Count('assigned_tasks', filter=Q(assigned_tasks__status='done')),
        )
        .order_by('-done_tasks')[:10]
    )
    chart_emp_labels = json.dumps([u.get_full_name() or u.username for u in executors], ensure_ascii=False)
    chart_emp_done = json.dumps([u.done_tasks for u in executors])
    chart_emp_total = json.dumps([u.total_tasks for u in executors])

    # 6. Задачи по статусам (Doughnut)
    task_status_labels = dict(Task.STATUS_CHOICES)
    tasks_by_status = list(
        Task.objects.values('status').annotate(count=Count('id')).order_by('-count')
    )
    chart_task_labels = json.dumps([task_status_labels.get(t['status'], t['status']) for t in tasks_by_status], ensure_ascii=False)
    chart_task_data = json.dumps([t['count'] for t in tasks_by_status])

    # ═══ Сводная статистика ═══
    total_revenue = ServiceRequest.objects.filter(status='COMPLETED').aggregate(
        total=Sum('budget_to'))['total'] or 0
    overdue_tasks = Task.objects.filter(
        due_date__lt=today, status__in=['backlog', 'todo', 'in_progress']
    ).count()
    active_projects = Project.objects.filter(status='active').count()
    avg_completion = Project.objects.filter(status='active').aggregate(
        avg=Avg('progress'))['avg'] or 0

    context = {
        'all_requests': all_requests[:10],
        'new_requests': new_requests[:5],
        'total_new': new_requests.count(),
        'total_all': all_requests.count(),
        'unassigned_tasks': unassigned_tasks[:5],
        'total_unassigned_tasks': unassigned_tasks.count(),
        # Сводная
        'total_revenue': total_revenue,
        'overdue_tasks': overdue_tasks,
        'active_projects': active_projects,
        'avg_completion': round(avg_completion, 1),
        # Диаграммы
        'chart_status_labels': chart_status_labels,
        'chart_status_data': chart_status_data,
        'chart_service_labels': chart_service_labels,
        'chart_service_data': chart_service_data,
        'chart_month_labels': chart_month_labels,
        'chart_month_data': chart_month_data,
        'chart_emp_labels': chart_emp_labels,
        'chart_emp_done': chart_emp_done,
        'chart_emp_total': chart_emp_total,
        'chart_task_labels': chart_task_labels,
        'chart_task_data': chart_task_data,
    }
    return render(request, 'accounts/dashboards/analyst.html', context)


@login_required
def executor_dashboard(request):
    """Личный кабинет исполнителя"""
    from tasks.models import Task
    from projects.models import Project
    
    my_tasks = Task.objects.filter(
        Q(assignee=request.user) | Q(assignments__assignee=request.user)
    ).distinct().order_by('-created_at')
    my_projects = Project.objects.filter(team=request.user).order_by('-created_at')
    
    context = {
        'my_tasks': my_tasks[:10],
        'my_projects': my_projects[:5],
        'tasks_in_progress': my_tasks.filter(status='in_progress').count(),
        'tasks_todo': my_tasks.filter(status='todo').count(),
        'tasks_done': my_tasks.filter(status='done').count(),
    }
    return render(request, 'accounts/dashboards/executor.html', context)


@login_required
def staff_list(request):
    """Страница сотрудников для аналитика / админа."""
    from core.models import UserSkill
    from tasks.models import Task

    # Только аналитики и админы видят список сотрудников
    if request.user.profile.role not in ('analyst', 'admin'):
        return redirect('accounts:dashboard')

    role_filter = request.GET.get('role', '')
    search_q = request.GET.get('q', '')

    staff_qs = User.objects.filter(
        profile__role__in=['analyst', 'executor']
    ).select_related('profile').annotate(
        total_tasks=Count('assigned_tasks'),
        active_tasks=Count(
            'assigned_tasks',
            filter=Q(assigned_tasks__status__in=['todo', 'in_progress']),
        ),
        done_tasks=Count(
            'assigned_tasks',
            filter=Q(assigned_tasks__status='done'),
        ),
    ).order_by('profile__role', 'first_name', 'last_name')

    if role_filter:
        staff_qs = staff_qs.filter(profile__role=role_filter)
    if search_q:
        staff_qs = staff_qs.filter(
            Q(first_name__icontains=search_q)
            | Q(last_name__icontains=search_q)
            | Q(username__icontains=search_q)
            | Q(profile__position__icontains=search_q)
        )

    # Собираем навыки для каждого сотрудника
    staff = []
    for u in staff_qs:
        skills = UserSkill.objects.filter(user=u).select_related('skill').order_by('-level')
        staff.append({
            'user': u,
            'profile': u.profile,
            'skills': skills,
            'total_tasks': u.total_tasks,
            'active_tasks': u.active_tasks,
            'done_tasks': u.done_tasks,
        })

    context = {
        'staff': staff,
        'role_filter': role_filter,
        'search_q': search_q,
        'total_analysts': User.objects.filter(profile__role='analyst').count(),
        'total_executors': User.objects.filter(profile__role='executor').count(),
    }
    return render(request, 'accounts/staff_list.html', context)

