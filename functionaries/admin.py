from django.contrib import admin

from core.admin_base import ModelAdmin

from .models import Functionary, FunctionaryRole


@admin.register(Functionary)
class FunctionaryAdmin(ModelAdmin):
    list_display = ('get_display_name', 'functionary_role', 'year')
    list_filter = ('functionary_role', 'year')
    search_fields = (
        'member__first_name',
        'member__last_name',
        'member__username',
        'member__email',
        'name',
        'functionary_role__title',
        'year',
    )
    autocomplete_fields = ('member', 'functionary_role')
    list_select_related = ('member', 'functionary_role')
    ordering = ['-year']
    fields = ('member', 'name', 'functionary_role', 'year')

    @admin.display(description='Namn')
    def get_display_name(self, obj):
        return obj.get_full_name()


@admin.register(FunctionaryRole)
class FunctionaryRoleAdmin(ModelAdmin):
    list_display = ('title', 'board')
    list_filter = ('board',)
    search_fields = ('title',)
    ordering = ['title']
