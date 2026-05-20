from django.contrib import admin

from .models import BusinessDocument, DocumentSignature


class DocumentSignatureInline(admin.TabularInline):
	model = DocumentSignature
	extra = 0
	readonly_fields = ('token', 'signed_at', 'ip_address')


@admin.register(BusinessDocument)
class BusinessDocumentAdmin(admin.ModelAdmin):
	list_display = ('number', 'doc_type', 'request', 'status', 'amount', 'issue_date', 'due_date')
	list_filter = ('doc_type', 'status', 'issue_date')
	search_fields = ('number', 'title', 'request__title')
	inlines = [DocumentSignatureInline]


@admin.register(DocumentSignature)
class DocumentSignatureAdmin(admin.ModelAdmin):
	list_display = ('document', 'signer', 'status', 'sent_at', 'signed_at', 'ip_address')
	list_filter = ('status',)
	search_fields = ('document__number', 'signer__username')
	readonly_fields = ('token',)
