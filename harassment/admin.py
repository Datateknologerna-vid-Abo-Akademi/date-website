from django.contrib import admin

from core.admin_base import ModelAdmin

from .models import Harassment, HarassmentEmailRecipient


class LegacySocialPermissionMixin:
    legacy_model_name = ''

    def _has_legacy_permission(self, request, action):
        return request.user.has_perm(f'social.{action}_{self.legacy_model_name}')

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


@admin.register(Harassment)
class HarassmentAdmin(LegacySocialPermissionMixin, ModelAdmin):
    legacy_model_name = 'harassment'
    list_display = ('email', 'message_preview')
    search_fields = ('email', 'message')

    @admin.display(description="Message")
    def message_preview(self, obj):
        return obj.message[:80] + '...' if len(obj.message) > 80 else obj.message


@admin.register(HarassmentEmailRecipient)
class HarassmentEmailRecipientAdmin(LegacySocialPermissionMixin, ModelAdmin):
    legacy_model_name = 'harassmentemailrecipient'
    list_display = ('recipient_email',)
    search_fields = ('recipient_email',)
    ordering = ('recipient_email',)
