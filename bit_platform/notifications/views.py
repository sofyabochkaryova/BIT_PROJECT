from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.core.paginator import Paginator
from django.db.models import Q
from .models import Notification, NotificationPreference


@login_required
def notification_list(request):
    """Список уведомлений пользователя"""
    notifications = Notification.objects.filter(recipient=request.user)
    
    # Фильтр по типу
    notification_type = request.GET.get('type')
    if notification_type:
        notifications = notifications.filter(notification_type=notification_type)
    
    # Фильтр по статусу прочтения
    status = request.GET.get('status')
    if status == 'unread':
        notifications = notifications.filter(is_read=False)
    elif status == 'read':
        notifications = notifications.filter(is_read=True)
    
    # Пагинация
    paginator = Paginator(notifications, 20)
    page = request.GET.get('page', 1)
    notifications = paginator.get_page(page)
    
    # Подсчёт непрочитанных
    unread_count = Notification.objects.filter(
        recipient=request.user, is_read=False
    ).count()
    
    context = {
        'notifications': notifications,
        'unread_count': unread_count,
        'current_type': notification_type,
        'current_status': status,
    }
    return render(request, 'notifications/list.html', context)


@login_required
@require_POST
def mark_as_read(request, pk):
    """Отметить уведомление как прочитанное"""
    notification = get_object_or_404(Notification, pk=pk, recipient=request.user)
    notification.mark_as_read()
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'success': True})
    return redirect('notifications:list')


@login_required
@require_POST
def mark_all_read(request):
    """Отметить все уведомления как прочитанные"""
    Notification.objects.filter(
        recipient=request.user, is_read=False
    ).update(is_read=True)
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'success': True})
    return redirect('notifications:list')


@login_required
@require_POST
def delete_notification(request, pk):
    """Удалить уведомление"""
    notification = get_object_or_404(Notification, pk=pk, recipient=request.user)
    notification.delete()
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'success': True})
    return redirect('notifications:list')


@login_required
@require_POST
def clear_all(request):
    """Удалить все прочитанные уведомления"""
    Notification.objects.filter(
        recipient=request.user, is_read=True
    ).delete()
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'success': True})
    return redirect('notifications:list')


@login_required
def get_unread_count(request):
    """API: получить количество непрочитанных"""
    count = Notification.objects.filter(
        recipient=request.user, is_read=False
    ).count()
    return JsonResponse({'count': count})


@login_required
def get_recent(request):
    """API: получить последние уведомления для dropdown"""
    notifications = Notification.objects.filter(
        recipient=request.user
    )[:5]
    
    data = [{
        'id': n.pk,
        'title': n.title,
        'message': n.message[:100],
        'type': n.notification_type,
        'icon': n.icon,
        'color': n.type_color,
        'is_read': n.is_read,
        'link': n.link,
        'created_at': n.created_at.strftime('%d.%m.%Y %H:%M'),
    } for n in notifications]
    
    unread_count = Notification.objects.filter(
        recipient=request.user, is_read=False
    ).count()
    
    return JsonResponse({
        'notifications': data,
        'unread_count': unread_count
    })


@login_required
def notification_preferences(request):
    """Настройки уведомлений"""
    prefs, created = NotificationPreference.objects.get_or_create(user=request.user)
    
    if request.method == 'POST':
        prefs.email_new_request = request.POST.get('email_new_request') == 'on'
        prefs.email_request_update = request.POST.get('email_request_update') == 'on'
        prefs.email_new_task = request.POST.get('email_new_task') == 'on'
        prefs.email_task_update = request.POST.get('email_task_update') == 'on'
        prefs.email_new_message = request.POST.get('email_new_message') == 'on'
        prefs.email_weekly_digest = request.POST.get('email_weekly_digest') == 'on'
        prefs.push_enabled = request.POST.get('push_enabled') == 'on'
        prefs.save()
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': True})
        return redirect('notifications:preferences')
    
    return render(request, 'notifications/preferences.html', {'preferences': prefs})


# Вспомогательная функция для создания уведомлений
def create_notification(recipient, title, message, notification_type='info', sender=None, link=''):
    """Создать уведомление"""
    return Notification.objects.create(
        recipient=recipient,
        sender=sender,
        notification_type=notification_type,
        title=title,
        message=message,
        link=link
    )
