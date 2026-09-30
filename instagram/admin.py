from django.contrib import admin

from core.admin_base import ModelAdmin

from .models import IgUrl


@admin.register(IgUrl)
class IgUrlAdmin(ModelAdmin):
    list_display = ('url', 'shortcode')
    search_fields = ('url', 'shortcode')
    ordering = ('url',)

    def _has_legacy_permission(self, request, action):
        return request.user.has_perm(f'social.{action}_igurl')

    def has_module_permission(self, request):
        if super().has_module_permission(request):
            return True
        return any(self._has_legacy_permission(request, action) for action in ('view', 'add', 'change', 'delete'))

    def has_view_permission(self, request, obj=None):
        return super().has_view_permission(request, obj) or self._has_legacy_permission(request, 'view')

    def has_add_permission(self, request):
        return super().has_add_permission(request) or self._has_legacy_permission(request, 'add')

    def has_change_permission(self, request, obj=None):
        return super().has_change_permission(request, obj) or self._has_legacy_permission(request, 'change')

    def has_delete_permission(self, request, obj=None):
        return super().has_delete_permission(request, obj) or self._has_legacy_permission(request, 'delete')
