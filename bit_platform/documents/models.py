from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


class BusinessDocument(models.Model):
	"""Бизнес-документы: КП, договор, акт, счёт."""

	TYPE_CHOICES = [
		('proposal', 'Коммерческое предложение'),
		('contract', 'Договор'),
		('act', 'Акт выполненных работ'),
		('invoice', 'Счёт на оплату'),
	]

	STATUS_CHOICES = [
		('draft', 'Черновик'),
		('issued', 'Выставлен'),
		('approved', 'Согласован'),
		('signed', 'Подписан'),
		('paid', 'Оплачен'),
		('cancelled', 'Отменён'),
	]

	request = models.ForeignKey(
		'requests_app.ServiceRequest',
		on_delete=models.CASCADE,
		related_name='business_documents',
		verbose_name='Заявка',
	)
	contract = models.ForeignKey(
		'contracts.Contract',
		on_delete=models.SET_NULL,
		null=True,
		blank=True,
		related_name='documents',
		verbose_name='Договор',
	)
	proposal = models.ForeignKey(
		'proposals.CommercialProposal',
		on_delete=models.SET_NULL,
		null=True,
		blank=True,
		related_name='documents',
		verbose_name='КП',
	)
	doc_type = models.CharField('Тип документа', max_length=20, choices=TYPE_CHOICES)
	number = models.CharField('Номер', max_length=60, unique=True)
	title = models.CharField('Название', max_length=255)
	amount = models.DecimalField('Сумма', max_digits=12, decimal_places=2, default=0)
	description = models.TextField('Содержимое', blank=True)
	status = models.CharField('Статус', max_length=20, choices=STATUS_CHOICES, default='draft')
	issue_date = models.DateField('Дата выставления', null=True, blank=True)
	due_date = models.DateField('Срок оплаты/подписания', null=True, blank=True)
	file = models.FileField('Файл', upload_to='business_documents/%Y/%m/', null=True, blank=True)
	created_by = models.ForeignKey(
		User,
		on_delete=models.SET_NULL,
		null=True,
		blank=True,
		related_name='created_business_documents',
		verbose_name='Создал',
	)
	created_at = models.DateTimeField('Создан', auto_now_add=True)
	updated_at = models.DateTimeField('Обновлён', auto_now=True)

	class Meta:
		verbose_name = 'Бизнес-документ'
		verbose_name_plural = 'Бизнес-документы'
		ordering = ['-created_at']
		unique_together = [('request', 'doc_type')]  # Один акт и один счет на заявку

	def __str__(self):
		return f'{self.number} ({self.get_doc_type_display()})'

	def save(self, *args, **kwargs):
		if not self.number:
			self.number = self._generate_number(self.doc_type)
		super().save(*args, **kwargs)

	@classmethod
	def _generate_number(cls, doc_type):
		prefix_map = {
			'proposal': 'КПД',
			'contract': 'ДГД',
			'act': 'АКТ',
			'invoice': 'СЧ',
		}
		prefix = prefix_map.get(doc_type, 'DOC')
		period = timezone.now().strftime('%Y%m')
		base = f'{prefix}-{period}-'
		seq = cls.objects.filter(number__startswith=base).count() + 1
		while True:
			number = f'{base}{seq:04d}'
			if not cls.objects.filter(number=number).exists():
				return number
			seq += 1


class DocumentSignature(models.Model):
	"""Запись о подписании документа."""

	STATUS_CHOICES = [
		('pending', 'Ожидает подписания'),
		('signed', 'Подписан'),
		('rejected', 'Отклонён'),
	]

	document = models.ForeignKey(
		BusinessDocument,
		on_delete=models.CASCADE,
		related_name='signatures',
		verbose_name='Документ',
	)
	signer = models.ForeignKey(
		User,
		on_delete=models.CASCADE,
		related_name='document_signatures',
		verbose_name='Подписант',
	)
	status = models.CharField('Статус', max_length=20, choices=STATUS_CHOICES, default='pending')
	token = models.CharField('Токен подписания', max_length=64, unique=True, blank=True)
	comment = models.TextField('Комментарий подписанта', blank=True)
	sent_at = models.DateTimeField('Отправлено на подписание', auto_now_add=True)
	signed_at = models.DateTimeField('Дата подписания', null=True, blank=True)
	ip_address = models.GenericIPAddressField('IP адрес подписанта', null=True, blank=True)

	class Meta:
		verbose_name = 'Подпись документа'
		verbose_name_plural = 'Подписи документов'
		ordering = ['-sent_at']
		unique_together = ['document', 'signer']

	def __str__(self):
		return f'{self.document.number} — {self.signer.get_full_name() or self.signer.username}'

	def save(self, *args, **kwargs):
		if not self.token:
			import secrets
			self.token = secrets.token_urlsafe(48)
		super().save(*args, **kwargs)
