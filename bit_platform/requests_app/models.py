from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal


class ServiceRequest(models.Model):
    """Заявка на услугу от клиента"""
    
    STATUS_CHOICES = [
        # Этап: анализ и КП
        ('IN_ANALYSIS', 'Аналитик изучает'),
        ('ESTIMATION', 'Оценка сроков/бюджета'),
        ('PROPOSAL_DRAFT', 'Подготовка КП'),
        ('PROPOSAL_SENT', 'КП отправлено'),
        ('CLIENT_REVIEW', 'Клиент рассматривает'),
        ('NEGOTIATION', 'Согласование условий'),
        # Этап: согласование
        ('CLIENT_APPROVED', 'Клиент одобрил'),
        ('INTERNAL_APPROVAL', 'Внутреннее согласование'),
        ('LEGAL_REVIEW', 'Юридическая проверка'),
        ('FINANCIAL_CHECK', 'Финансовый контроль'),
        ('CONTRACT_DRAFT', 'Подготовка договора'),
        # Этап: договор
        ('CONTRACT_SENT', 'Договор отправлен'),
        ('CONTRACT_SIGNED', 'Подписан сторонами'),
        ('ADVANCE_PAYMENT', 'Поступил аванс'),
        # Этап: реализация
        ('CONVERTED', 'Конвертирован в проект'),
        ('IN_PROGRESS', 'Работы ведутся'),
        ('COMPLETED', 'Завершен'),
        # Терминальные
        ('REJECTED', 'Отклонен'),
        ('CANCELLED', 'Отменен клиентом'),
        ('ARCHIVED', 'В архиве'),
    ]
    
    SERVICE_CHOICES = [
        ('outsourcing', 'IT-аутсорсинг'),
        ('implementation', 'Внедрение ПО'),
        ('consulting', 'IT-консалтинг'),
        ('development', 'Разработка ПО'),
        ('security', 'Информационная безопасность'),
        ('network', 'Сетевые решения'),
        ('cloud', 'Облачные сервисы'),
        ('training', 'Обучение персонала'),
        ('other', 'Другое'),
    ]
    
    PRIORITY_CHOICES = [
        ('low', 'Низкий'),
        ('medium', 'Средний'),
        ('high', 'Высокий'),
        ('urgent', 'Срочный'),
    ]
    
    # Основная информация
    number = models.CharField('Номер заявки', max_length=40, unique=True, blank=True)
    title = models.CharField('Название заявки', max_length=200)
    service_type = models.CharField('Тип услуги', max_length=50, choices=SERVICE_CHOICES)
    description = models.TextField('Описание задачи')
    
    # Клиент
    client = models.ForeignKey(User, on_delete=models.CASCADE, related_name='requests', verbose_name='Клиент')
    client_company = models.ForeignKey(
        'clients.ClientCompany', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='requests', verbose_name='Компания клиента',
    )
    company_name = models.CharField('Название компании', max_length=200, blank=True)
    contact_phone = models.CharField('Контактный телефон', max_length=20)
    contact_email = models.EmailField('Email для связи')
    
    # Статус и приоритет
    status = models.CharField('Статус', max_length=32, choices=STATUS_CHOICES, default='IN_ANALYSIS')
    priority = models.CharField('Приоритет', max_length=20, choices=PRIORITY_CHOICES, default='medium')
    
    # Назначения
    analyst = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='analyzed_requests', verbose_name='Аналитик'
    )
    executor = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='executed_requests', verbose_name='Исполнитель'
    )
    
    # Бюджет и сроки
    budget_from = models.DecimalField('Бюджет от', max_digits=12, decimal_places=2, null=True, blank=True)
    budget_to = models.DecimalField('Бюджет до', max_digits=12, decimal_places=2, null=True, blank=True)
    deadline = models.DateField('Желаемый срок', null=True, blank=True)
    sla_due_at = models.DateTimeField('SLA срок обработки', null=True, blank=True)
    automation_recommendation = models.TextField('Рекомендации автоматизации', blank=True)
    deadline_reminder_sent_at = models.DateTimeField('Напоминание по дедлайну отправлено', null=True, blank=True)
    
    # Даты
    created_at = models.DateTimeField('Дата создания', auto_now_add=True)
    updated_at = models.DateTimeField('Дата обновления', auto_now=True)
    completed_at = models.DateTimeField('Дата завершения', null=True, blank=True)
    
    class Meta:
        verbose_name = 'Заявка'
        verbose_name_plural = 'Заявки'
        ordering = ['-created_at']
    
    def __str__(self):
        return f'{self.number or f"#{self.pk}"} - {self.title}'

    def save(self, *args, **kwargs):
        if not self.number:
            self.number = self._generate_number()
        super().save(*args, **kwargs)

    @classmethod
    def _generate_number(cls):
        period = timezone.now().strftime('%Y%m')
        base = f'SR-{period}-'
        seq = cls.objects.filter(number__startswith=base).count() + 1
        while True:
            number = f'{base}{seq:04d}'
            if not cls.objects.filter(number=number).exists():
                return number
            seq += 1
    
    @property
    def status_color(self):
        colors = {
            'IN_ANALYSIS': 'warning',
            'ESTIMATION': 'info',
            'PROPOSAL_DRAFT': 'secondary',
            'PROPOSAL_SENT': 'primary',
            'CLIENT_REVIEW': 'info',
            'NEGOTIATION': 'primary',
            'CLIENT_APPROVED': 'success',
            'INTERNAL_APPROVAL': 'info',
            'LEGAL_REVIEW': 'secondary',
            'FINANCIAL_CHECK': 'secondary',
            'CONTRACT_DRAFT': 'secondary',
            'CONTRACT_SENT': 'info',
            'CONTRACT_SIGNED': 'success',
            'ADVANCE_PAYMENT': 'success',
            'CONVERTED': 'primary',
            'IN_PROGRESS': 'primary',
            'COMPLETED': 'success',
            'REJECTED': 'danger',
            'CANCELLED': 'danger',
            'ARCHIVED': 'secondary',
        }
        return colors.get(self.status, 'secondary')

    @property
    def is_complex(self):
        return (
            self.priority in ['high', 'urgent'] or
            (self.budget_to and self.budget_to >= 500000)
        )

    # Разрешённые переходы с учётом отката
    ALLOWED_TRANSITIONS = {
        'IN_ANALYSIS': {'ESTIMATION', 'PROPOSAL_DRAFT', 'REJECTED', 'CANCELLED'},
        'ESTIMATION': {'PROPOSAL_DRAFT', 'IN_ANALYSIS', 'REJECTED', 'CANCELLED'},
        'PROPOSAL_DRAFT': {'PROPOSAL_SENT', 'ESTIMATION', 'IN_ANALYSIS', 'REJECTED', 'CANCELLED'},
        'PROPOSAL_SENT': {'CLIENT_REVIEW', 'CLIENT_APPROVED', 'NEGOTIATION', 'PROPOSAL_DRAFT', 'REJECTED', 'CANCELLED'},
        'CLIENT_REVIEW': {'CLIENT_APPROVED', 'NEGOTIATION', 'PROPOSAL_DRAFT', 'REJECTED', 'CANCELLED'},
        'NEGOTIATION': {'CLIENT_APPROVED', 'PROPOSAL_DRAFT', 'REJECTED', 'CANCELLED'},
        'CLIENT_APPROVED': {'INTERNAL_APPROVAL', 'NEGOTIATION', 'REJECTED', 'CANCELLED'},
        'INTERNAL_APPROVAL': {'LEGAL_REVIEW', 'FINANCIAL_CHECK', 'NEGOTIATION', 'REJECTED', 'CANCELLED'},
        'LEGAL_REVIEW': {'FINANCIAL_CHECK', 'CONTRACT_DRAFT', 'NEGOTIATION', 'REJECTED', 'CANCELLED'},
        'FINANCIAL_CHECK': {'CONTRACT_DRAFT', 'NEGOTIATION', 'REJECTED', 'CANCELLED'},
        'CONTRACT_DRAFT': {'CONTRACT_SENT', 'NEGOTIATION', 'REJECTED', 'CANCELLED'},
        'CONTRACT_SENT': {'CONTRACT_SIGNED', 'CONTRACT_DRAFT', 'NEGOTIATION', 'REJECTED', 'CANCELLED'},
        'CONTRACT_SIGNED': {'ADVANCE_PAYMENT', 'CONTRACT_SENT', 'REJECTED', 'CANCELLED'},
        'ADVANCE_PAYMENT': {'CONVERTED', 'IN_PROGRESS', 'REJECTED', 'CANCELLED'},
        'CONVERTED': {'IN_PROGRESS', 'REJECTED', 'CANCELLED'},
        'IN_PROGRESS': {'COMPLETED', 'REJECTED', 'CANCELLED'},
        'COMPLETED': {'ARCHIVED'},
        'REJECTED': {'ARCHIVED'},
        'CANCELLED': {'ARCHIVED'},
        'ARCHIVED': set(),
    }

    ROLE_TRANSITIONS = {
        'analyst': {
            'IN_ANALYSIS', 'ESTIMATION', 'PROPOSAL_DRAFT', 'PROPOSAL_SENT', 'CLIENT_REVIEW',
            'NEGOTIATION', 'REJECTED', 'CANCELLED',
        },
        'executor': {'IN_PROGRESS', 'COMPLETED'},
        'admin': set(),  # Админ может всё
    }

    def ensure_approval_workflow(self):
        """Создаёт базовые шаги согласования для сложной заявки."""
        if self.approvals.exists():
            return

        base_steps = [
            ('triage', 'Первичный разбор'),
            ('estimation', 'Оценка сроков и трудозатрат'),
            ('technical', 'Техническая экспертиза'),
        ]

        if self.is_complex:
            base_steps.extend([
                ('finance', 'Финансовое согласование'),
                ('legal', 'Юридическое согласование'),
            ])

        base_steps.append(('client_confirmation', 'Подтверждение клиента'))

        for index, (step_type, title) in enumerate(base_steps, start=1):
            RequestApproval.objects.create(
                request=self,
                order=index,
                step_type=step_type,
                title=title,
            )

    def can_transition(self, user, new_status):
        """Проверяет право и возможность смены статуса с учётом ролей и карты переходов."""
        if new_status == self.status:
            return True

        allowed_targets = self.ALLOWED_TRANSITIONS.get(self.status, set())
        if new_status not in allowed_targets:
            return False

        profile = getattr(user, 'profile', None)
        role = getattr(profile, 'role', None)

        if role == 'admin':
            return True

        if role == 'analyst' and new_status in self.ROLE_TRANSITIONS['analyst']:
            return True

        if role == 'executor' and new_status in self.ROLE_TRANSITIONS['executor']:
            return True

        # Клиент может только отменить
        if role == 'client' and new_status in ['CANCELLED'] and self.client_id == user.id:
            return True

        return False

    def change_status(self, new_status, changed_by, comment='', force=False):
        """Меняет статус с записью истории и отправкой напоминаний."""
        if not force and not self.can_transition(changed_by, new_status):
            raise ValueError('Недостаточно прав или недопустимый переход статуса')

        old_status = self.status
        self.status = new_status
        self.save(update_fields=['status', 'updated_at'])

        RequestStatusHistory.objects.create(
            request=self,
            old_status=old_status,
            new_status=new_status,
            changed_by=changed_by,
            comment=comment or '',
        )

        self.ensure_deadline_reminder(changed_by)

    def run_auto_triage(self):
        """Автоматически рассчитывает рекомендации и SLA для заявки."""
        service_defaults = {
            'outsourcing': (150000, 450000, 20),
            'implementation': (300000, 1200000, 45),
            'consulting': (80000, 300000, 14),
            'development': (250000, 1500000, 60),
            'security': (350000, 1300000, 35),
            'network': (200000, 800000, 30),
            'cloud': (180000, 700000, 25),
            'training': (60000, 220000, 10),
            'other': (100000, 500000, 20),
        }

        recommended_from, recommended_to, recommended_days = service_defaults.get(
            self.service_type,
            (100000, 500000, 20),
        )

        if not self.budget_from:
            self.budget_from = recommended_from
        if not self.budget_to:
            self.budget_to = recommended_to

        if not self.deadline:
            self.deadline = timezone.now().date() + timedelta(days=recommended_days)

        priority_sla_hours = {
            'urgent': 2,
            'high': 6,
            'medium': 24,
            'low': 48,
        }
        self.sla_due_at = timezone.now() + timedelta(hours=priority_sla_hours.get(self.priority, 24))

        budget_from = int(self.budget_from or 0)
        budget_to = int(self.budget_to or 0)
        self.automation_recommendation = (
            f'Рекомендуемый диапазон бюджета: {int(self.budget_from)}–{int(self.budget_to)} ₽; '
            f'рекомендуемый срок: до {self.deadline.strftime("%d.%m.%Y")}; '
            f'SLA первичной реакции до {self.sla_due_at.strftime("%d.%m.%Y %H:%M")}. '
            f'Рекомендуемый следующий шаг: {self.get_status_display()} → Анализ → КП.'
        )

        if self.is_complex:
            self.automation_recommendation += ' Заявка классифицирована как сложная: требуется расширенное согласование (финансы/юристы).'
        if Decimal(str(budget_to or 0)) >= Decimal('1000000'):
            self.automation_recommendation += ' Рекомендация: вынести проект на этапное финансирование с контрольными точками.'

    def auto_assign_team(self):
        """Автоматическое назначение аналитика и исполнителя по минимальной загрузке."""
        from django.db.models import Count, Q

        active_statuses = [
            'IN_ANALYSIS', 'ESTIMATION', 'PROPOSAL_DRAFT', 'PROPOSAL_SENT', 'CLIENT_REVIEW', 'NEGOTIATION',
            'CLIENT_APPROVED', 'INTERNAL_APPROVAL', 'LEGAL_REVIEW', 'FINANCIAL_CHECK', 'CONTRACT_DRAFT',
            'CONTRACT_SENT', 'CONTRACT_SIGNED', 'ADVANCE_PAYMENT', 'CONVERTED', 'IN_PROGRESS'
        ]

        exclude_ids = []
        if self.client_id:
            exclude_ids.append(self.client_id)

        analyst_candidate = (
            User.objects.filter(profile__role='analyst')
            .exclude(pk__in=exclude_ids)
            .annotate(
                active_requests=Count(
                    'analyzed_requests',
                    filter=Q(analyzed_requests__status__in=active_statuses),
                )
            )
            .order_by('active_requests', 'date_joined')
            .first()
        )

        executor_candidate = (
            User.objects.filter(profile__role='executor')
            .exclude(pk__in=exclude_ids)
            .annotate(
                active_requests=Count(
                    'executed_requests',
                    filter=Q(executed_requests__status__in=active_statuses),
                )
            )
            .order_by('active_requests', 'date_joined')
            .first()
        )

        if not self.analyst and analyst_candidate:
            self.analyst = analyst_candidate
        if not self.executor and executor_candidate:
            self.executor = executor_candidate

        return self.analyst, self.executor

    def apply_routing_rules(self):
        """Применяет правила маршрутизации для назначения аналитика и исполнителя."""
        rules = RequestRoutingRule.objects.filter(is_active=True).order_by('order', 'id')
        applied = False

        for rule in rules:
            if not rule.matches(self):
                continue

            if rule.assign_analyst and not self.analyst and rule.assign_analyst_id != self.client_id:
                self.analyst = rule.assign_analyst
                applied = True
            if rule.assign_executor and not self.executor and rule.assign_executor_id != self.client_id:
                self.executor = rule.assign_executor
                applied = True

            if applied:
                break

        return applied

    def auto_assign_approval_owners(self):
        """Автоматическое назначение ответственных по этапам согласования."""
        if not self.approvals.exists():
            return

        finance_owner = User.objects.filter(profile__role='analyst').order_by('date_joined').first()
        legal_owner = User.objects.filter(profile__role='admin').order_by('date_joined').first()

        for approval in self.approvals.all():
            if approval.assigned_to:
                continue

            if approval.step_type in ['triage', 'estimation', 'technical']:
                approval.assigned_to = self.analyst
            elif approval.step_type == 'finance':
                approval.assigned_to = finance_owner or self.analyst
            elif approval.step_type == 'legal':
                approval.assigned_to = legal_owner or self.analyst
            elif approval.step_type == 'client_confirmation':
                approval.assigned_to = self.client

            approval.save(update_fields=['assigned_to', 'updated_at'])

    def ensure_deadline_reminder(self, actor):
        """Отправляет напоминание, если дедлайн близко и ещё не напоминали."""
        if not self.deadline or self.deadline_reminder_sent_at:
            return

        days_left = (self.deadline - timezone.now().date()).days
        if days_left < 0:
            return

        if days_left <= 2:
            self.deadline_reminder_sent_at = timezone.now()
            self.save(update_fields=['deadline_reminder_sent_at', 'updated_at'])

            try:
                from notifications.views import create_notification
                create_notification(
                    recipient=self.client,
                    title='Напоминание о сроке',
                    message=f'Заявка {self.number}: срок {self.deadline.strftime("%d.%m.%Y")}',
                    notification_type='request',
                    sender=actor,
                    link=f'/requests/{self.pk}/',
                )
            except Exception:
                pass


class RequestRoutingRule(models.Model):
    """Правила маршрутизации заявок для контролируемого назначения."""

    name = models.CharField('Название правила', max_length=200)
    order = models.PositiveIntegerField('Порядок применения', default=1)
    is_active = models.BooleanField('Активно', default=True)

    service_type = models.CharField(
        'Тип услуги', max_length=50, choices=ServiceRequest.SERVICE_CHOICES, blank=True
    )
    priority = models.CharField(
        'Приоритет', max_length=20, choices=ServiceRequest.PRIORITY_CHOICES, blank=True
    )
    min_budget = models.DecimalField('Мин. бюджет', max_digits=12, decimal_places=2, null=True, blank=True)
    max_budget = models.DecimalField('Макс. бюджет', max_digits=12, decimal_places=2, null=True, blank=True)

    assign_analyst = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='routing_rules_as_analyst', verbose_name='Назначить аналитика'
    )
    assign_executor = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='routing_rules_as_executor', verbose_name='Назначить исполнителя'
    )

    created_at = models.DateTimeField('Создано', auto_now_add=True)
    updated_at = models.DateTimeField('Обновлено', auto_now=True)

    class Meta:
        verbose_name = 'Правило маршрутизации заявки'
        verbose_name_plural = 'Правила маршрутизации заявок'
        ordering = ['order', 'id']

    def __str__(self):
        return f'{self.name} (#{self.order})'

    def matches(self, service_request: ServiceRequest) -> bool:
        if not self.is_active:
            return False

        if self.service_type and service_request.service_type != self.service_type:
            return False

        if self.priority and service_request.priority != self.priority:
            return False

        budget_ceiling = service_request.budget_to or service_request.budget_from or Decimal('0')

        if self.min_budget and budget_ceiling < self.min_budget:
            return False

        if self.max_budget and budget_ceiling > self.max_budget:
            return False

        return True


class RequestComment(models.Model):
    """Комментарий к заявке"""
    
    request = models.ForeignKey(ServiceRequest, on_delete=models.CASCADE, related_name='comments')
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name='request_comments')
    text = models.TextField('Комментарий')
    is_internal = models.BooleanField('Внутренний комментарий', default=False)
    created_at = models.DateTimeField('Дата', auto_now_add=True)
    
    class Meta:
        verbose_name = 'Комментарий'
        verbose_name_plural = 'Комментарии'
        ordering = ['created_at']
    
    def __str__(self):
        return f'Комментарий от {self.author.username}'


class RequestStatusHistory(models.Model):
    """История смен статусов заявки."""

    request = models.ForeignKey(
        ServiceRequest,
        on_delete=models.CASCADE,
        related_name='status_history',
        verbose_name='Заявка',
    )
    old_status = models.CharField('Было', max_length=32, blank=True)
    new_status = models.CharField('Стало', max_length=32)
    changed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='status_changes',
        verbose_name='Изменил',
    )
    comment = models.TextField('Комментарий', blank=True)
    changed_at = models.DateTimeField('Изменено', auto_now_add=True)

    class Meta:
        verbose_name = 'История статусов заявки'
        verbose_name_plural = 'История статусов заявок'
        ordering = ['-changed_at']

    def __str__(self):
        return f'{self.request_id}: {self.old_status} → {self.new_status}'

    def _display_for(self, code):
        labels = dict(ServiceRequest.STATUS_CHOICES)
        return labels.get(code, code or '—')

    def get_old_display(self):
        return self._display_for(self.old_status)

    def get_new_display(self):
        return self._display_for(self.new_status)


class RequestAttachment(models.Model):
    """Вложение к заявке"""
    
    request = models.ForeignKey(ServiceRequest, on_delete=models.CASCADE, related_name='attachments')
    file = models.FileField('Файл', upload_to='request_attachments/')
    filename = models.CharField('Имя файла', max_length=255)
    uploaded_by = models.ForeignKey(User, on_delete=models.CASCADE)
    uploaded_at = models.DateTimeField('Дата загрузки', auto_now_add=True)
    
    class Meta:
        verbose_name = 'Вложение'
        verbose_name_plural = 'Вложения'
    
    def __str__(self):
        return self.filename


class RequestApproval(models.Model):
    """Шаг согласования заявки."""

    STEP_CHOICES = [
        ('triage', 'Первичный разбор'),
        ('estimation', 'Оценка'),
        ('technical', 'Техническое согласование'),
        ('finance', 'Финансовое согласование'),
        ('legal', 'Юридическое согласование'),
        ('client_confirmation', 'Подтверждение клиента'),
    ]

    STATUS_CHOICES = [
        ('pending', 'Ожидает'),
        ('approved', 'Согласовано'),
        ('rejected', 'Отклонено'),
        ('rework', 'На доработке'),
    ]

    request = models.ForeignKey(
        ServiceRequest,
        on_delete=models.CASCADE,
        related_name='approvals',
        verbose_name='Заявка',
    )
    order = models.PositiveIntegerField('Порядок', default=1)
    step_type = models.CharField('Тип этапа', max_length=40, choices=STEP_CHOICES)
    title = models.CharField('Название этапа', max_length=200)
    status = models.CharField('Статус', max_length=20, choices=STATUS_CHOICES, default='pending')
    assigned_to = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='request_approvals',
        verbose_name='Ответственный',
    )
    comment = models.TextField('Комментарий', blank=True)
    decided_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='decided_request_approvals',
        verbose_name='Согласовал',
    )
    decided_at = models.DateTimeField('Дата решения', null=True, blank=True)
    created_at = models.DateTimeField('Создан', auto_now_add=True)
    updated_at = models.DateTimeField('Обновлён', auto_now=True)

    class Meta:
        verbose_name = 'Согласование заявки'
        verbose_name_plural = 'Согласования заявок'
        ordering = ['order', 'created_at']
        unique_together = [('request', 'order')]

    def __str__(self):
        return f'#{self.request_id} [{self.order}] {self.title}'
