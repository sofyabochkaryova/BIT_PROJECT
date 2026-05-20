from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


class CommercialProposal(models.Model):
	"""Коммерческое предложение (КП)."""

	STATUS_CHOICES = [
		('draft', 'Черновик'),
		('internal_review', 'Внутреннее согласование'),
		('sent', 'Отправлено клиенту'),
		('accepted', 'Принято клиентом'),
		('rejected', 'Отклонено клиентом'),
	]

	request = models.ForeignKey(
		'requests_app.ServiceRequest',
		on_delete=models.CASCADE,
		related_name='proposals',
		verbose_name='Заявка',
	)
	author = models.ForeignKey(
		User,
		on_delete=models.CASCADE,
		related_name='proposals',
		verbose_name='Автор',
	)
	number = models.CharField('Номер КП', max_length=50, unique=True)
	title = models.CharField('Название', max_length=200)
	scope = models.TextField('Объём работ')
	assumptions = models.TextField('Предположения и ограничения', blank=True)
	total_amount = models.DecimalField('Итоговая стоимость', max_digits=12, decimal_places=2, default=0)
	duration_days = models.PositiveIntegerField('Срок реализации (дней)', default=0)
	status = models.CharField('Статус', max_length=20, choices=STATUS_CHOICES, default='draft')
	valid_until = models.DateField('Действительно до', null=True, blank=True)
	created_at = models.DateTimeField('Создано', auto_now_add=True)
	updated_at = models.DateTimeField('Обновлено', auto_now=True)

	class Meta:
		verbose_name = 'Коммерческое предложение'
		verbose_name_plural = 'Коммерческие предложения'
		ordering = ['-created_at']

	def __str__(self):
		return f'{self.number} - {self.title}'

	def save(self, *args, **kwargs):
		if not self.number:
			self.number = self._generate_number()
		super().save(*args, **kwargs)

	@classmethod
	def _generate_number(cls):
		period = timezone.now().strftime('%Y%m')
		base = f'КП-{period}-'
		seq = cls.objects.filter(number__startswith=base).count() + 1
		while True:
			number = f'{base}{seq:04d}'
			if not cls.objects.filter(number=number).exists():
				return number
			seq += 1


class ProposalItem(models.Model):
	"""Позиция КП."""

	proposal = models.ForeignKey(
		CommercialProposal,
		on_delete=models.CASCADE,
		related_name='items',
		verbose_name='КП',
	)
	stage_name = models.CharField('Этап', max_length=150)
	description = models.TextField('Описание')
	quantity = models.DecimalField('Количество', max_digits=10, decimal_places=2, default=1)
	unit = models.CharField('Ед. изм.', max_length=30, default='усл. ед.')
	unit_price = models.DecimalField('Цена за единицу', max_digits=12, decimal_places=2, default=0)
	total_price = models.DecimalField('Сумма', max_digits=12, decimal_places=2, default=0)
	order = models.PositiveIntegerField('Порядок', default=1)

	class Meta:
		verbose_name = 'Позиция КП'
		verbose_name_plural = 'Позиции КП'
		ordering = ['order', 'id']

	def save(self, *args, **kwargs):
		self.total_price = self.quantity * self.unit_price
		super().save(*args, **kwargs)

	def __str__(self):
		return f'{self.proposal.number}: {self.stage_name}'

# Create your models here.
