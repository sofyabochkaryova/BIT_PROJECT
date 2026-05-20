from django.db import models
from django.contrib.auth.models import User


class Task(models.Model):
    """Задача"""
    
    STATUS_CHOICES = [
        ('backlog', 'Бэклог'),
        ('todo', 'К выполнению'),
        ('in_progress', 'В работе'),
        ('review', 'На проверке'),
        ('done', 'Выполнена'),
    ]
    
    PRIORITY_CHOICES = [
        ('low', 'Низкий'),
        ('medium', 'Средний'),
        ('high', 'Высокий'),
        ('critical', 'Критический'),
    ]
    
    TYPE_CHOICES = [
        ('task', 'Задача'),
        ('bug', 'Баг'),
        ('feature', 'Фича'),
        ('improvement', 'Улучшение'),
    ]
    
    # Основное
    title = models.CharField('Название', max_length=200)
    description = models.TextField('Описание', blank=True)
    task_type = models.CharField('Тип', max_length=20, choices=TYPE_CHOICES, default='task')
    
    # Связи
    project = models.ForeignKey(
        'projects.Project', on_delete=models.CASCADE, 
        related_name='tasks', verbose_name='Проект'
    )
    service_request = models.ForeignKey(
        'requests_app.ServiceRequest', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='tasks', verbose_name='Заявка'
    )
    parent_task = models.ForeignKey(
        'self', on_delete=models.CASCADE, null=True, blank=True,
        related_name='subtasks', verbose_name='Родительская задача'
    )
    
    # Назначения
    assignee = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='assigned_tasks', verbose_name='Исполнитель'
    )
    created_by = models.ForeignKey(
        User, on_delete=models.CASCADE,
        related_name='created_tasks', verbose_name='Автор'
    )
    
    # Статус и приоритет
    status = models.CharField('Статус', max_length=20, choices=STATUS_CHOICES, default='backlog')
    priority = models.CharField('Приоритет', max_length=20, choices=PRIORITY_CHOICES, default='medium')
    
    # Оценка и время
    estimated_hours = models.DecimalField('Оценка (часы)', max_digits=6, decimal_places=2, null=True, blank=True)
    spent_hours = models.DecimalField('Затрачено (часы)', max_digits=6, decimal_places=2, default=0)
    
    # Сроки
    due_date = models.DateField('Дедлайн', null=True, blank=True)
    
    # Даты
    created_at = models.DateTimeField('Дата создания', auto_now_add=True)
    updated_at = models.DateTimeField('Дата обновления', auto_now=True)
    completed_at = models.DateTimeField('Дата завершения', null=True, blank=True)
    
    class Meta:
        verbose_name = 'Задача'
        verbose_name_plural = 'Задачи'
        ordering = ['-created_at']
    
    def __str__(self):
        return f'{self.project.name} - {self.title}'
    
    @property
    def status_color(self):
        colors = {
            'backlog': 'secondary',
            'todo': 'info',
            'in_progress': 'primary',
            'review': 'warning',
            'done': 'success',
        }
        return colors.get(self.status, 'secondary')
    
    @property
    def priority_color(self):
        colors = {
            'low': 'secondary',
            'medium': 'info',
            'high': 'warning',
            'critical': 'danger',
        }
        return colors.get(self.priority, 'secondary')


class TaskComment(models.Model):
    """Комментарий к задаче"""
    
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='comments')
    author = models.ForeignKey(User, on_delete=models.CASCADE)
    text = models.TextField('Комментарий')
    created_at = models.DateTimeField('Дата', auto_now_add=True)
    
    class Meta:
        verbose_name = 'Комментарий'
        verbose_name_plural = 'Комментарии'
        ordering = ['created_at']
    
    def __str__(self):
        return f'Комментарий от {self.author.username}'


class TaskAssignment(models.Model):
    """Этап задачи, закреплённый за конкретным исполнителем."""

    STAGE_CHOICES = [
        ('analysis', 'Анализ'),
        ('backend', 'Backend'),
        ('frontend', 'Frontend'),
        ('qa', 'Тестирование'),
        ('deploy', 'Внедрение'),
        ('support', 'Поддержка'),
    ]

    STATUS_CHOICES = [
        ('todo', 'К выполнению'),
        ('in_progress', 'В работе'),
        ('review', 'На проверке'),
        ('done', 'Выполнено'),
    ]

    task = models.ForeignKey(
        Task,
        on_delete=models.CASCADE,
        related_name='assignments',
        verbose_name='Задача',
    )
    assignee = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='task_assignments',
        verbose_name='Исполнитель',
    )
    stage = models.CharField('Этап', max_length=30, choices=STAGE_CHOICES)
    status = models.CharField('Статус этапа', max_length=20, choices=STATUS_CHOICES, default='todo')
    description = models.TextField('Описание этапа', blank=True)
    planned_start = models.DateField('План старт', null=True, blank=True)
    planned_end = models.DateField('План завершение', null=True, blank=True)
    actual_start = models.DateField('Факт старт', null=True, blank=True)
    actual_end = models.DateField('Факт завершение', null=True, blank=True)
    order = models.PositiveIntegerField('Порядок этапа', default=1)
    created_at = models.DateTimeField('Создан', auto_now_add=True)
    updated_at = models.DateTimeField('Обновлён', auto_now=True)

    class Meta:
        verbose_name = 'Назначение этапа задачи'
        verbose_name_plural = 'Назначения этапов задач'
        ordering = ['order', 'created_at']
        unique_together = [('task', 'assignee', 'stage')]

    def __str__(self):
        return f'{self.task_id}: {self.get_stage_display()} -> {self.assignee.username}'
