
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


class TimeEntry(models.Model):
    """Запись учёта рабочего времени по задаче."""

    task = models.ForeignKey(
        'tasks.Task', on_delete=models.CASCADE,
        related_name='time_entries', verbose_name='Задача',
    )
    user = models.ForeignKey(
        User, on_delete=models.CASCADE,
        related_name='time_entries', verbose_name='Исполнитель',
    )
    date = models.DateField('Дата', default=timezone.now)
    hours = models.DecimalField('Часы', max_digits=5, decimal_places=2)
    description = models.TextField('Что сделано')
    created_at = models.DateTimeField('Создано', auto_now_add=True)
    updated_at = models.DateTimeField('Обновлено', auto_now=True)

    class Meta:
        verbose_name = 'Запись времени'
        verbose_name_plural = 'Записи времени'
        ordering = ['-date', '-created_at']

    def __str__(self):
        return f'{self.user.username}: {self.hours}ч @ {self.task.title} ({self.date})'

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # Обновляем spent_hours в задаче
        total = self.task.time_entries.aggregate(s=models.Sum('hours'))['s'] or 0
        self.task.spent_hours = total
        self.task.save(update_fields=['spent_hours', 'updated_at'])


class WorkReport(models.Model):
    """Отчёт исполнителя о проделанной работе по задаче / проекту."""

    STATUS_CHOICES = [
        ('draft', 'Черновик'),
        ('submitted', 'На проверке'),
        ('accepted', 'Принят'),
        ('revision', 'На доработке'),
    ]

    task = models.ForeignKey(
        'tasks.Task', on_delete=models.CASCADE,
        related_name='work_reports', verbose_name='Задача',
    )
    author = models.ForeignKey(
        User, on_delete=models.CASCADE,
        related_name='work_reports', verbose_name='Автор',
    )
    title = models.CharField('Заголовок', max_length=255)
    content = models.TextField('Содержание отчёта')
    hours_total = models.DecimalField('Затрачено часов', max_digits=6, decimal_places=2, default=0)
    status = models.CharField('Статус', max_length=20, choices=STATUS_CHOICES, default='draft')

    # Рецензия аналитика
    reviewer = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='reviewed_reports', verbose_name='Проверил',
    )
    review_comment = models.TextField('Комментарий проверяющего', blank=True)
    reviewed_at = models.DateTimeField('Дата проверки', null=True, blank=True)

    created_at = models.DateTimeField('Создано', auto_now_add=True)
    updated_at = models.DateTimeField('Обновлено', auto_now=True)

    class Meta:
        verbose_name = 'Отчёт о работе'
        verbose_name_plural = 'Отчёты о работе'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.title} ({self.get_status_display()})'
