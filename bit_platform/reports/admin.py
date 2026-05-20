from django.contrib import admin
from .models import Report, DashboardWidget, ActivityLog


@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    list_display = ('name', 'report_type', 'created_by', 'date_from', 'date_to', 'created_at')
    list_filter = ('report_type', 'file_format', 'is_scheduled', 'created_at')
    search_fields = ('name', 'description', 'created_by__username')
    raw_id_fields = ('created_by',)
    readonly_fields = ('created_at', 'updated_at')
    date_hierarchy = 'created_at'


@admin.register(DashboardWidget)
class DashboardWidgetAdmin(admin.ModelAdmin):
    list_display = ('name', 'widget_type', 'data_source', 'visible_to', 'order', 'is_active')
    list_filter = ('widget_type', 'is_active', 'visible_to')
    search_fields = ('name', 'description')
    list_editable = ('order', 'is_active')


@admin.register(ActivityLog)
class ActivityLogAdmin(admin.ModelAdmin):
    list_display = ('user', 'action', 'content_type', 'object_repr', 'ip_address', 'created_at')
    list_filter = ('action', 'content_type', 'created_at')
    search_fields = ('user__username', 'object_repr', 'ip_address')
    raw_id_fields = ('user',)
    readonly_fields = ('created_at',)
    date_hierarchy = 'created_at'
