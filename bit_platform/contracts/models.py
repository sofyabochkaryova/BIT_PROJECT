from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


class Contract(models.Model):
	"""Договор с клиентом."""

	STATUS_CHOICES = [
		('draft', 'Черновик'),
		('legal_review', 'Юр. согласование'),
		('sent', 'Отправлен на подпись'),
		('signed', 'Подписан'),
		('active', 'Действует'),
		('closed', 'Закрыт'),
		('terminated', 'Расторгнут'),
	]

	request = models.ForeignKey(
		'requests_app.ServiceRequest',
		on_delete=models.CASCADE,
		related_name='contracts',
		verbose_name='Заявка',
	)
	proposal = models.ForeignKey(
		'proposals.CommercialProposal',
		on_delete=models.SET_NULL,
		null=True,
		blank=True,
		related_name='contracts',
		verbose_name='КП',
	)
	responsible = models.ForeignKey(
		User,
		on_delete=models.SET_NULL,
		null=True,
		blank=True,
		related_name='managed_contracts',
		verbose_name='Ответственный',
	)
	number = models.CharField('Номер договора', max_length=50, unique=True)
	subject = models.CharField('Предмет договора', max_length=255)
	amount = models.DecimalField('Сумма договора', max_digits=12, decimal_places=2, default=0)
	start_date = models.DateField('Дата начала', null=True, blank=True)
	end_date = models.DateField('Дата окончания', null=True, blank=True)
	payment_terms = models.TextField('Условия оплаты', blank=True)
	status = models.CharField('Статус', max_length=20, choices=STATUS_CHOICES, default='draft')
	created_at = models.DateTimeField('Создан', auto_now_add=True)
	updated_at = models.DateTimeField('Обновлён', auto_now=True)

	class Meta:
		verbose_name = 'Договор'
		verbose_name_plural = 'Договоры'
		ordering = ['-created_at']

	def __str__(self):
		return self.number

	def save(self, *args, **kwargs):
		if not self.number:
			self.number = self._generate_number()
		super().save(*args, **kwargs)

	@classmethod
	def _generate_number(cls):
		period = timezone.now().strftime('%Y%m')
		base = f'ДГ-{period}-'
		seq = cls.objects.filter(number__startswith=base).count() + 1
		while True:
			number = f'{base}{seq:04d}'
			if not cls.objects.filter(number=number).exists():
				return number
			seq += 1

# Create your models here.
