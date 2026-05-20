from django.contrib import admin

from .models import CommercialProposal, ProposalItem


class ProposalItemInline(admin.TabularInline):
	model = ProposalItem
	extra = 0


@admin.register(CommercialProposal)
class CommercialProposalAdmin(admin.ModelAdmin):
	list_display = ('number', 'title', 'request', 'author', 'status', 'total_amount', 'created_at')
	list_filter = ('status', 'created_at')
	search_fields = ('number', 'title', 'request__title')
	inlines = [ProposalItemInline]


@admin.register(ProposalItem)
class ProposalItemAdmin(admin.ModelAdmin):
	list_display = ('proposal', 'stage_name', 'quantity', 'unit_price', 'total_price')
	search_fields = ('proposal__number', 'stage_name')

# Register your models here.
