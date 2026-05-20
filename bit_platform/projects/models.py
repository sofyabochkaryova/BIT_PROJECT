from django.db import models
from django.contrib.auth.models import User


class Project(models.Model):
    """Проект"""
    
    STATUS_CHOICES = [
        ('planning', 'Планирование'),
        ('active', 'В работе'),
        ('on_hold', 'Приостановлен'),
        ('completed', 'Завершён'),
        ('archived', 'В архиве'),
        ('cancelled', 'Отменён'),
    ]
    
    name = models.CharField('Название проекта', max_length=200)
    description = models.TextField('Описание', blank=True)
    
    # Связи
    client = models.ForeignKey(User, on_delete=models.CASCADE, related_name='client_projects', verbose_name='Клиент')
    service_request = models.ForeignKey(
        'requests_app.ServiceRequest', on_delete=models.SET_NULL, 
        null=True, blank=True, related_name='projects', verbose_name='Заявка'
    )
    
    # Команда
    manager = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='managed_projects', verbose_name='Менеджер проекта'
    )
    team = models.ManyToManyField(User, related_name='team_projects', blank=True, verbose_name='Команда')
    
    # Статус и сроки
    status = models.CharField('Статус', max_length=20, choices=STATUS_CHOICES, default='planning')
    start_date = models.DateField('Дата начала', null=True, blank=True)
    end_date = models.DateField('Дата окончания', null=True, blank=True)
    
    # Бюджет
    budget = models.DecimalField('Бюджет', max_digits=12, decimal_places=2, null=True, blank=True)
    
    # Прогресс
    progress = models.PositiveIntegerField('Прогресс %', default=0)
    
    # Даты
    created_at = models.DateTimeField('Дата создания', auto_now_add=True)
    updated_at = models.DateTimeField('Дата обновления', auto_now=True)
    
    class Meta:
        verbose_name = 'Проект'
        verbose_name_plural = 'Проекты'
        ordering = ['-created_at']
    
    def __str__(self):
        return self.name
    
    @property
    def status_color(self):
        colors = {
            'planning': 'secondary',
            'active': 'primary',
            'on_hold': 'warning',
            'completed': 'success',
            'archived': 'dark',
            'cancelled': 'danger',
        }
        return colors.get(self.status, 'secondary')
    
    @property
    def progress_color(self):
        """Определяет цвет прогресс-бара на основе процента выполнения"""
        if self.progress >= 75:
            return 'success'
        elif self.progress >= 50:
            return 'info'
        elif self.progress >= 25:
            return 'warning'
        else:
            return 'danger'
