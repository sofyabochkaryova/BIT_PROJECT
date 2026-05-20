from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


class Notification(models.Model):
    """Уведомление пользователя"""
    
    TYPE_CHOICES = [
        ('info', 'Информация'),
        ('success', 'Успех'),
        ('warning', 'Предупреждение'),
        ('error', 'Ошибка'),
        ('request', 'Заявка'),
        ('task', 'Задача'),
        ('project', 'Проект'),
        ('message', 'Сообщение'),
        ('system', 'Системное'),
    ]
    
    ICON_MAP = {
        'info': 'fa-info-circle',
        'success': 'fa-check-circle',
        'warning': 'fa-exclamation-triangle',
        'error': 'fa-times-circle',
        'request': 'fa-file-alt',
        'task': 'fa-tasks',
        'project': 'fa-project-diagram',
        'message': 'fa-envelope',
        'system': 'fa-cog',
    }
    
    recipient = models.ForeignKey(
        User, on_delete=models.CASCADE,
        related_name='notifications', verbose_name='Получатель'
    )
    sender = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='sent_notifications', verbose_name='Отправитель'
    )
    
    notification_type = models.CharField('Тип', max_length=20, choices=TYPE_CHOICES, default='info')
    title = models.CharField('Заголовок', max_length=200)
    message = models.TextField('Сообщение')
    
    # Ссылка на объект
    link = models.CharField('Ссылка', max_length=500, blank=True)
    
    # Статус
    is_read = models.BooleanField('Прочитано', default=False)
    read_at = models.DateTimeField('Время прочтения', null=True, blank=True)
    
    # Даты
    created_at = models.DateTimeField('Создано', auto_now_add=True)
    
    class Meta:
        verbose_name = 'Уведомление'
        verbose_name_plural = 'Уведомления'
        ordering = ['-created_at']
    
    def __str__(self):
        return f'{self.recipient.username}: {self.title}'
    
    @property
    def icon(self):
        return self.ICON_MAP.get(self.notification_type, 'fa-bell')
    
    @property
    def type_color(self):
        colors = {
            'info': 'primary',
            'success': 'success',
            'warning': 'warning',
            'error': 'danger',
            'request': 'info',
            'task': 'purple',
            'project': 'secondary',
            'message': 'primary',
            'system': 'dark',
        }
        return colors.get(self.notification_type, 'primary')
    
    def mark_as_read(self):
        if not self.is_read:
            self.is_read = True
            self.read_at = timezone.now()
            self.save()


class NotificationPreference(models.Model):
    """Настройки уведомлений пользователя"""
    
    user = models.OneToOneField(
        User, on_delete=models.CASCADE,
        related_name='notification_preferences', verbose_name='Пользователь'
    )
    
    # Email уведомления
    email_new_request = models.BooleanField('Email о новых заявках', default=True)
    email_request_update = models.BooleanField('Email об изменениях заявок', default=True)
    email_new_task = models.BooleanField('Email о новых задачах', default=True)
    email_task_update = models.BooleanField('Email об изменениях задач', default=True)
    email_new_message = models.BooleanField('Email о новых сообщениях', default=True)
    email_weekly_digest = models.BooleanField('Еженедельная сводка', default=True)
    
    # Push уведомления
    push_enabled = models.BooleanField('Push уведомления', default=True)
    
    class Meta:
        verbose_name = 'Настройки уведомлений'
        verbose_name_plural = 'Настройки уведомлений'
    
    def __str__(self):
        return f'Настройки {self.user.username}'
