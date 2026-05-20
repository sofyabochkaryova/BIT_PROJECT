from django.contrib import admin
from .models import ClientCompany


@admin.register(ClientCompany)
class ClientCompanyAdmin(admin.ModelAdmin):
    list_display = ('short_name', 'inn', 'director_name', 'owner', 'created_at')
    list_filter = ('legal_form',)
    search_fields = ('short_name', 'full_name', 'inn')
    fieldsets = (
        ('Основное', {'fields': ('owner', 'short_name', 'full_name', 'legal_form')}),
        ('Реквизиты', {'fields': ('inn', 'kpp', 'ogrn')}),
        ('Адреса', {'fields': ('legal_address', 'actual_address')}),
        ('Банк', {'fields': ('bank_name', 'bik', 'corr_account', 'settlement_account')}),
        ('Руководитель', {'fields': ('director_name', 'director_position', 'director_basis')}),
        ('Контакты', {'fields': ('phone', 'email', 'website')}),
        ('Печать и подпись', {'fields': ('stamp_image', 'signature_image')}),
    )
