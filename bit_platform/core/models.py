"""
Шаблоны проектов и навыки специалистов.

Позволяет:
- автоматически подбирать типовые этапы работ на основе типа услуги
- хранить навыки исполнителей
- подбирать альтернативных исполнителей по похожим навыкам
"""

from django.db import models
from django.contrib.auth.models import User

from requests_app.models import ServiceRequest


class Skill(models.Model):
    """Навык / компетенция (Python, 1С, сети, и т.д.)."""
    name = models.CharField('Название', max_length=100, unique=True)
    category = models.CharField('Категория', max_length=60, blank=True)

    class Meta:
        verbose_name = 'Навык'
        verbose_name_plural = 'Навыки'
        ordering = ['category', 'name']

    def __str__(self):
        return self.name


class UserSkill(models.Model):
    """Связь «пользователь — навык — уровень»."""
    LEVEL_CHOICES = [
        (1, 'Начальный'),
        (2, 'Средний'),
        (3, 'Продвинутый'),
        (4, 'Эксперт'),
    ]
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='skills')
    skill = models.ForeignKey(Skill, on_delete=models.CASCADE, related_name='users')
    level = models.PositiveSmallIntegerField('Уровень', choices=LEVEL_CHOICES, default=2)

    class Meta:
        verbose_name = 'Навык пользователя'
        verbose_name_plural = 'Навыки пользователей'
        unique_together = ['user', 'skill']

    def __str__(self):
        return f'{self.user.username} — {self.skill.name} ({self.get_level_display()})'


class ProjectTemplate(models.Model):
    """Шаблон проекта.  Привязывается к типу услуги ServiceRequest."""
    service_type = models.CharField(
        'Тип услуги', max_length=50,
        choices=ServiceRequest.SERVICE_CHOICES,
        unique=True,
    )
    name = models.CharField('Название шаблона', max_length=200)
    description = models.TextField('Описание', blank=True)
    default_duration_days = models.PositiveIntegerField('Типовой срок (дней)', default=30)

    class Meta:
        verbose_name = 'Шаблон проекта'
        verbose_name_plural = 'Шаблоны проектов'

    def __str__(self):
        return self.name


class ProjectTemplateStage(models.Model):
    """Типовой этап внутри шаблона проекта."""
    STAGE_CHOICES = [
        ('analysis', 'Анализ'),
        ('backend', 'Backend-разработка'),
        ('frontend', 'Frontend-разработка'),
        ('integration', 'Интеграция'),
        ('testing', 'Тестирование'),
        ('deploy', 'Внедрение'),
        ('training', 'Обучение'),
        ('support', 'Поддержка'),
        ('consulting', 'Консалтинг'),
        ('security', 'Аудит безопасности'),
        ('other', 'Другое'),
    ]

    template = models.ForeignKey(
        ProjectTemplate, on_delete=models.CASCADE,
        related_name='stages',
    )
    name = models.CharField('Этап', max_length=200)
    stage_type = models.CharField('Тип этапа', max_length=30, choices=STAGE_CHOICES, default='other')
    description = models.TextField('Описание работ', blank=True)
    order = models.PositiveIntegerField('Порядок', default=1)
    default_hours = models.DecimalField('Типовые часы', max_digits=6, decimal_places=1, default=8)
    default_unit_price = models.DecimalField('Базовая цена за час', max_digits=10, decimal_places=2, default=3000)
    required_skills = models.ManyToManyField(Skill, blank=True, related_name='template_stages', verbose_name='Нужные навыки')

    class Meta:
        verbose_name = 'Этап шаблона'
        verbose_name_plural = 'Этапы шаблона'
        ordering = ['order']

    def __str__(self):
        return f'{self.template.name} → {self.name}'
