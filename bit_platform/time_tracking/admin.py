from django.contrib import admin
from .models import TimeEntry, WorkReport


@admin.register(TimeEntry)
class TimeEntryAdmin(admin.ModelAdmin):
    list_display = ['user', 'task', 'date', 'hours', 'description']
    list_filter = ['date', 'user']
    search_fields = ['description', 'task__title']


@admin.register(WorkReport)
class WorkReportAdmin(admin.ModelAdmin):
    list_display = ['title', 'author', 'task', 'status', 'hours_total', 'created_at']
    list_filter = ['status']
    search_fields = ['title', 'content']
