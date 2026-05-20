from django.contrib import admin
from .models import Task, TaskComment, TaskAssignment


class TaskCommentInline(admin.TabularInline):
    """Инлайн для комментариев к задаче"""
    model = TaskComment
    extra = 0
    readonly_fields = ('author', 'created_at')


class TaskAssignmentInline(admin.TabularInline):
    model = TaskAssignment
    extra = 0
    raw_id_fields = ('assignee',)


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    """Админка задач"""
    list_display = ('title', 'project', 'assignee', 'status', 'priority', 'task_type', 'due_date')
    list_filter = ('status', 'priority', 'task_type', 'created_at')
    search_fields = ('title', 'description', 'project__name', 'assignee__username', 'created_by__username')
    raw_id_fields = ('project', 'assignee', 'created_by', 'service_request')
    readonly_fields = ('created_at', 'updated_at')
    date_hierarchy = 'created_at'
    inlines = [TaskCommentInline, TaskAssignmentInline]
    
    fieldsets = (
        ('Основная информация', {
            'fields': ('title', 'description', 'task_type')
        }),
        ('Статус и приоритет', {
            'fields': ('status', 'priority', 'due_date')
        }),
        ('Связи', {
            'fields': ('project', 'service_request')
        }),
        ('Исполнители', {
            'fields': ('assignee', 'created_by')
        }),
        ('Оценка времени', {
            'fields': ('estimated_hours', 'spent_hours')
        }),
        ('Даты', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def save_model(self, request, obj, form, change):
        if not change and not obj.created_by:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(TaskComment)
class TaskCommentAdmin(admin.ModelAdmin):
    """Админка комментариев к задачам"""
    list_display = ('task', 'author', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('text', 'author__username', 'task__title')
    raw_id_fields = ('task', 'author')
    readonly_fields = ('created_at',)


@admin.register(TaskAssignment)
class TaskAssignmentAdmin(admin.ModelAdmin):
    list_display = ('task', 'stage', 'assignee', 'status', 'planned_start', 'planned_end', 'order')
    list_filter = ('stage', 'status')
    search_fields = ('task__title', 'assignee__username')
    raw_id_fields = ('task', 'assignee')
