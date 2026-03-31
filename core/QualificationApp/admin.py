from django.contrib import admin
from .models import (
    Profession, GeneralizedLaborFunction, LaborFunction, 
    LaborFunctionDetails, Post, Employee, 
    EmployeeSkillProgress, Project, Task, SkillLog, ParserSettings,
    Notification
)

class LaborFunctionDetailsInline(admin.TabularInline):
    model = LaborFunctionDetails
    extra = 0
    fields = ('type', 'code', 'name')

class LaborFunctionInline(admin.TabularInline):
    model = LaborFunction
    extra = 0
    show_change_link = True

class GeneralizedLaborFunctionInline(admin.TabularInline):
    model = GeneralizedLaborFunction
    extra = 0
    show_change_link = True

@admin.register(Profession)
class ProfessionAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'publish_date')
    search_fields = ('name', 'code')
    inlines = [GeneralizedLaborFunctionInline]

@admin.register(GeneralizedLaborFunction)
class GLFAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'profession')
    list_filter = ('profession',)
    inlines = [LaborFunctionInline]

@admin.register(LaborFunction)
class LFAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'generalized_function')
    list_filter = ('generalized_function__profession',)
    inlines = [LaborFunctionDetailsInline]

@admin.register(LaborFunctionDetails)
class DetailsAdmin(admin.ModelAdmin):
    list_display = ('type', 'code', 'name', 'labor_function')
    list_filter = ('type', 'labor_function__generalized_function__profession')
    search_fields = ('name', 'code')

@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = ('name',)
    filter_horizontal = ('generalized_functions',)

class EmployeeSkillInline(admin.TabularInline):
    model = EmployeeSkillProgress
    extra = 0
    fields = ('get_function', 'skill_detail', 'level')
    readonly_fields = ('get_function', 'skill_detail')
    
    ordering = ('skill_detail__labor_function',)

    def get_function(self, obj):
        return obj.skill_detail.labor_function.name
    
    get_function.short_description = 'Трудовая функция'

@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    list_display = ('name', 'post', 'is_admin')
    list_filter = ('post',)
    search_fields = ('name',)
    inlines = [EmployeeSkillInline]
    
@admin.register(ParserSettings)
class ParserSettingsAdmin(admin.ModelAdmin):
    list_display = ('folder_path', 'last_update')
    
    def has_add_permission(self, request):
        return not ParserSettings.objects.exists()

admin.site.register(EmployeeSkillProgress)
admin.site.register(Project)
admin.site.register(Task)
admin.site.register(SkillLog)
admin.site.register(Notification)