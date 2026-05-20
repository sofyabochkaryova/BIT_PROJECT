from django.contrib import admin

from .models import Contract


@admin.register(Contract)
class ContractAdmin(admin.ModelAdmin):
	list_display = ('number', 'request', 'responsible', 'status', 'amount', 'start_date', 'end_date')
	list_filter = ('status', 'start_date', 'end_date')
	search_fields = ('number', 'subject', 'request__title')

# Register your models here.
