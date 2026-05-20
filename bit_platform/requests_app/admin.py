from django.contrib import admin
from .models import (
    ServiceRequest,
    RequestComment,
    RequestAttachment,
    RequestApproval,
    RequestRoutingRule,
    RequestStatusHistory,
)


class RequestCommentInline(admin.TabularInline):
    """Инлайн для комментариев к заявке"""
    model = RequestComment
    extra = 0
    readonly_fields = ('author', 'created_at')


class RequestAttachmentInline(admin.TabularInline):
    """Инлайн для вложений"""
    model = RequestAttachment
    extra = 0
    readonly_fields = ('uploaded_by', 'uploaded_at')


class RequestApprovalInline(admin.TabularInline):
    model = RequestApproval
    extra = 0
    readonly_fields = ('decided_at', 'created_at', 'updated_at')


@admin.register(ServiceRequest)
class ServiceRequestAdmin(admin.ModelAdmin):
    """Админка заявок на услуги"""
    list_display = ('id', 'title', 'client', 'service_type', 'status', 'priority', 'analyst', 'created_at')
    list_filter = ('status', 'service_type', 'priority', 'created_at')
    search_fields = ('title', 'description', 'client__username', 'analyst__username')
    raw_id_fields = ('client', 'analyst', 'executor')
    readonly_fields = ('created_at', 'updated_at')
    date_hierarchy = 'created_at'
    inlines = [RequestCommentInline, RequestAttachmentInline, RequestApprovalInline]
    
    fieldsets = (
        ('Основная информация', {
            'fields': ('title', 'description', 'service_type')
        }),
        ('Статус и приоритет', {
            'fields': ('status', 'priority', 'deadline')
        }),
        ('Участники', {
            'fields': ('client', 'analyst', 'executor')
        }),
        ('Даты', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def save_model(self, request, obj, form, change):
        if not change and not obj.client:
            obj.client = request.user
        super().save_model(request, obj, form, change)


@admin.register(RequestComment)
class RequestCommentAdmin(admin.ModelAdmin):
    """Админка комментариев"""
    list_display = ('request', 'author', 'is_internal', 'created_at')
    list_filter = ('is_internal', 'created_at')
    search_fields = ('text', 'author__username', 'request__title')
    raw_id_fields = ('request', 'author')
    readonly_fields = ('created_at',)


@admin.register(RequestAttachment)
class RequestAttachmentAdmin(admin.ModelAdmin):
    """Админка вложений"""
    list_display = ('request', 'file', 'uploaded_by', 'uploaded_at')
    list_filter = ('uploaded_at',)
    search_fields = ('request__title', 'uploaded_by__username')
    raw_id_fields = ('request', 'uploaded_by')
    readonly_fields = ('uploaded_at',)


@admin.register(RequestApproval)
class RequestApprovalAdmin(admin.ModelAdmin):
    list_display = ('request', 'order', 'title', 'status', 'assigned_to', 'decided_by', 'decided_at')
    list_filter = ('status', 'step_type', 'created_at')
    search_fields = ('request__title', 'title', 'comment')
    raw_id_fields = ('request', 'assigned_to', 'decided_by')
    ordering = ('request', 'order')


@admin.register(RequestRoutingRule)
class RequestRoutingRuleAdmin(admin.ModelAdmin):
    list_display = (
        'name', 'order', 'is_active', 'service_type', 'priority', 'min_budget', 'max_budget',
        'assign_analyst', 'assign_executor'
    )
    list_filter = ('is_active', 'service_type', 'priority')
    search_fields = ('name',)
    raw_id_fields = ('assign_analyst', 'assign_executor')
    ordering = ('order', 'id')


@admin.register(RequestStatusHistory)
class RequestStatusHistoryAdmin(admin.ModelAdmin):
    list_display = ('request', 'old_status', 'new_status', 'changed_by', 'changed_at')
    list_filter = ('new_status', 'old_status', 'changed_at')
    search_fields = ('request__title', 'comment')
    raw_id_fields = ('request', 'changed_by')
    ordering = ('-changed_at',)
