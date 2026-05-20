from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


class Report(models.Model):
    """Сохранённый отчёт"""
    
    TYPE_CHOICES = [
        ('requests', 'Отчёт по заявкам'),
        ('projects', 'Отчёт по проектам'),
        ('tasks', 'Отчёт по задачам'),
        ('users', 'Отчёт по пользователям'),
        ('financial', 'Финансовый отчёт'),
        ('custom', 'Пользовательский отчёт'),
    ]
    
    FORMAT_CHOICES = [
        ('pdf', 'PDF'),
        ('xlsx', 'Excel'),
        ('excel', 'Excel (legacy)'),
        ('csv', 'CSV'),
    ]
    
    name = models.CharField('Название', max_length=200)
    report_type = models.CharField('Тип отчёта', max_length=20, choices=TYPE_CHOICES)
    description = models.TextField('Описание', blank=True)
    
    # Параметры отчёта
    date_from = models.DateField('Период с', null=True, blank=True)
    date_to = models.DateField('Период по', null=True, blank=True)
    filters = models.JSONField('Фильтры', default=dict, blank=True)
    
    # Файл отчёта
    file = models.FileField('Файл', upload_to='reports/%Y/%m/', blank=True, null=True)
    file_format = models.CharField('Формат', max_length=10, choices=FORMAT_CHOICES, default='xlsx')
    
    # Метаданные
    created_by = models.ForeignKey(
        User, on_delete=models.CASCADE,
        related_name='reports', verbose_name='Автор'
    )
    is_scheduled = models.BooleanField('Запланирован', default=False)
    schedule = models.CharField('Расписание', max_length=50, blank=True)  # cron-формат
    
    created_at = models.DateTimeField('Создан', auto_now_add=True)
    updated_at = models.DateTimeField('Обновлён', auto_now=True)
    
    class Meta:
        verbose_name = 'Отчёт'
        verbose_name_plural = 'Отчёты'
        ordering = ['-created_at']
    
    def __str__(self):
        return f'{self.name} ({self.get_report_type_display()})'


class DashboardWidget(models.Model):
    """Виджет для дашборда аналитики"""
    
    TYPE_CHOICES = [
        ('counter', 'Счётчик'),
        ('chart_line', 'Линейный график'),
        ('chart_bar', 'Столбчатая диаграмма'),
        ('chart_pie', 'Круговая диаграмма'),
        ('chart_doughnut', 'Кольцевая диаграмма'),
        ('table', 'Таблица'),
        ('list', 'Список'),
    ]
    
    name = models.CharField('Название', max_length=100)
    widget_type = models.CharField('Тип виджета', max_length=20, choices=TYPE_CHOICES)
    description = models.CharField('Описание', max_length=200, blank=True)
    
    # Источник данных
    data_source = models.CharField('Источник данных', max_length=50)  # requests, projects, tasks...
    metric = models.CharField('Метрика', max_length=50)  # count, sum, avg...
    
    # Настройки отображения
    color = models.CharField('Цвет', max_length=20, default='primary')
    icon = models.CharField('Иконка', max_length=50, default='fa-chart-bar')
    size = models.CharField('Размер', max_length=20, default='col-md-6 col-lg-3')
    
    # Порядок и видимость
    order = models.PositiveIntegerField('Порядок', default=0)
    is_active = models.BooleanField('Активен', default=True)
    
    # Привязка к роли (кому показывать)
    visible_to = models.CharField('Показывать для', max_length=20, blank=True)  # client, analyst, executor, admin, all
    
    class Meta:
        verbose_name = 'Виджет дашборда'
        verbose_name_plural = 'Виджеты дашборда'
        ordering = ['order']
    
    def __str__(self):
        return self.name


class ActivityLog(models.Model):
    """Лог активности пользователей"""
    
    ACTION_CHOICES = [
        ('create', 'Создание'),
        ('update', 'Изменение'),
        ('delete', 'Удаление'),
        ('view', 'Просмотр'),
        ('login', 'Вход'),
        ('logout', 'Выход'),
        ('comment', 'Комментарий'),
        ('status_change', 'Изменение статуса'),
    ]
    
    user = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True,
        related_name='activity_logs', verbose_name='Пользователь'
    )
    action = models.CharField('Действие', max_length=20, choices=ACTION_CHOICES)
    
    # Объект действия
    content_type = models.CharField('Тип объекта', max_length=50)  # request, project, task...
    object_id = models.PositiveIntegerField('ID объекта', null=True, blank=True)
    object_repr = models.CharField('Представление объекта', max_length=200, blank=True)
    
    # Детали
    details = models.JSONField('Детали', default=dict, blank=True)
    ip_address = models.GenericIPAddressField('IP адрес', null=True, blank=True)
    user_agent = models.CharField('User Agent', max_length=500, blank=True)
    
    created_at = models.DateTimeField('Время', auto_now_add=True)
    
    class Meta:
        verbose_name = 'Лог активности'
        verbose_name_plural = 'Логи активности'
        ordering = ['-created_at']
    
    def __str__(self):
        return f'{self.user} - {self.get_action_display()} - {self.content_type}'
