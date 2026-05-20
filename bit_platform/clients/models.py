from django.db import models
from django.contrib.auth.models import User


class ClientCompany(models.Model):
    """Компания клиента с полными юридическими реквизитами."""

    FORM_CHOICES = [
        ('ooo', 'ООО'),
        ('ip', 'ИП'),
        ('ao', 'АО'),
        ('pao', 'ПАО'),
        ('oao', 'ОАО'),
        ('zao', 'ЗАО'),
        ('other', 'Другое'),
    ]

    # Связь
    owner = models.ForeignKey(
        User, on_delete=models.CASCADE,
        related_name='companies', verbose_name='Владелец (клиент)',
    )

    # Название
    short_name = models.CharField('Краткое наименование', max_length=200,
                                  help_text='Например: ООО «Рога и Копыта»')
    full_name = models.CharField('Полное наименование', max_length=400, blank=True,
                                 help_text='Общество с ограниченной ответственностью «Рога и Копыта»')
    legal_form = models.CharField('Орг.-правовая форма', max_length=10,
                                  choices=FORM_CHOICES, default='ooo')

    # Реквизиты
    inn = models.CharField('ИНН', max_length=12, blank=True)
    kpp = models.CharField('КПП', max_length=9, blank=True)
    ogrn = models.CharField('ОГРН / ОГРНИП', max_length=15, blank=True)

    # Адреса
    legal_address = models.TextField('Юридический адрес', blank=True)
    actual_address = models.TextField('Фактический адрес', blank=True)

    # Банковские реквизиты
    bank_name = models.CharField('Наименование банка', max_length=200, blank=True)
    bik = models.CharField('БИК', max_length=9, blank=True)
    corr_account = models.CharField('Кор. счёт', max_length=20, blank=True)
    settlement_account = models.CharField('Расчётный счёт', max_length=20, blank=True)

    # Руководитель
    director_name = models.CharField('ФИО руководителя', max_length=200, blank=True)
    director_position = models.CharField('Должность руководителя', max_length=100,
                                         default='Генеральный директор')
    director_basis = models.CharField('Действует на основании', max_length=100,
                                      default='Устава')

    # Контакты
    phone = models.CharField('Телефон', max_length=30, blank=True)
    email = models.EmailField('Email', blank=True)
    website = models.URLField('Сайт', blank=True)

    # Файлы подписи и печати
    stamp_image = models.ImageField('Печать (PNG, прозрачный фон)',
                                    upload_to='company_stamps/', blank=True, null=True)
    signature_image = models.ImageField('Подпись руководителя (PNG, прозрачный фон)',
                                        upload_to='company_signatures/', blank=True, null=True)

    created_at = models.DateTimeField('Создано', auto_now_add=True)
    updated_at = models.DateTimeField('Обновлено', auto_now=True)

    class Meta:
        verbose_name = 'Компания клиента'
        verbose_name_plural = 'Компании клиентов'
        ordering = ['short_name']

    def __str__(self):
        return self.short_name

    @property
    def bank_details_str(self):
        """Банковские реквизиты одной строкой."""
        parts = []
        if self.settlement_account:
            parts.append(f'Р/с {self.settlement_account}')
        if self.bank_name:
            parts.append(self.bank_name)
        if self.bik:
            parts.append(f'БИК {self.bik}')
        if self.corr_account:
            parts.append(f'К/с {self.corr_account}')
        return ', '.join(parts)

    @property
    def requisites_block(self):
        """Полный блок реквизитов для документов."""
        lines = [self.short_name]
        if self.inn:
            s = f'ИНН {self.inn}'
            if self.kpp:
                s += f' / КПП {self.kpp}'
            lines.append(s)
        if self.ogrn:
            lines.append(f'ОГРН {self.ogrn}')
        if self.legal_address:
            lines.append(self.legal_address)
        if self.bank_details_str:
            lines.append(self.bank_details_str)
        return '\n'.join(lines)
