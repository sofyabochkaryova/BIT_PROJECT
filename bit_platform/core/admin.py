from django.contrib import admin

from .models import Skill, UserSkill, ProjectTemplate, ProjectTemplateStage


@admin.register(Skill)
class SkillAdmin(admin.ModelAdmin):
    list_display = ('name', 'category')
    list_filter = ('category',)
    search_fields = ('name',)


@admin.register(UserSkill)
class UserSkillAdmin(admin.ModelAdmin):
    list_display = ('user', 'skill', 'level')
    list_filter = ('level', 'skill__category')
    search_fields = ('user__username', 'skill__name')


class ProjectTemplateStageInline(admin.TabularInline):
    model = ProjectTemplateStage
    extra = 1
    fields = ('order', 'name', 'stage_type', 'default_hours', 'default_unit_price', 'description')


@admin.register(ProjectTemplate)
class ProjectTemplateAdmin(admin.ModelAdmin):
    list_display = ('name', 'service_type', 'default_duration_days')
    inlines = [ProjectTemplateStageInline]
