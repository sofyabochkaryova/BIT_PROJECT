from django.contrib import admin
from .models import Project


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    """Админка проектов"""
    list_display = ('name', 'client', 'manager', 'status', 'progress', 'start_date', 'end_date')
    list_filter = ('status', 'start_date', 'end_date')
    search_fields = ('name', 'description', 'client__username', 'manager__username')
    raw_id_fields = ('client', 'manager', 'team')
    readonly_fields = ('created_at', 'updated_at')
    date_hierarchy = 'start_date'
    filter_horizontal = ('team',)
    
    fieldsets = (
        ('Основная информация', {
            'fields': ('name', 'description')
        }),
        ('Статус и прогресс', {
            'fields': ('status', 'progress')
        }),
        ('Сроки', {
            'fields': ('start_date', 'end_date')
        }),
        ('Участники', {
            'fields': ('client', 'manager', 'team')
        }),
        ('Даты создания/изменения', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
