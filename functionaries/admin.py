from django.conf import settings
from django.contrib import admin
from django.db.models import Count
from django.urls import reverse
from django.utils.html import format_html
from django.utils.http import urlencode
from django.utils.translation import gettext_lazy as _
from django.utils.translation import ngettext

from core.admin import (
    ActiveLanguageTranslationAdminMixin,
    LanguageTabbedTranslationAdmin,
    TranslationCompletionAdminMixin,
)
from core.admin_base import ExtraChangeListLinksMixin, ModelAdmin, TabularInline
from core.admin_ui import AdminLink

from .models import Functionary, FunctionaryRole


class LegacyFunctionaryPermissionMixin:
    legacy_model_name = ''

    def _has_legacy_permission(self, request, action):
        return request.user.has_perm(f'members.{action}_{self.legacy_model_name}')

    def has_module_permission(self, request):
        if super().has_module_permission(request):
            return True
        return any(self._has_legacy_permission(request, action) for action in ('view', 'add', 'change', 'delete'))

    def has_view_permission(self, request, obj=None):
        return super().has_view_permission(request, obj) or self._has_legacy_permission(request, 'view')

    def has_add_permission(self, request, obj=None):
        current_permission = (
            super().has_add_permission(request, obj)
            if isinstance(self, admin.options.InlineModelAdmin)
            else super().has_add_permission(request)
        )
        return current_permission or self._has_legacy_permission(request, 'add')

    def has_change_permission(self, request, obj=None):
        return super().has_change_permission(request, obj) or self._has_legacy_permission(request, 'change')

    def has_delete_permission(self, request, obj=None):
        return super().has_delete_permission(request, obj) or self._has_legacy_permission(request, 'delete')


if settings.ENABLE_LANGUAGE_FEATURES:  # type: ignore[misc]

    class FunctionaryRoleTranslationAdminBase(
        ActiveLanguageTranslationAdminMixin, LanguageTabbedTranslationAdmin, ModelAdmin
    ):
        pass
else:
    FunctionaryRoleTranslationAdminBase = ModelAdmin  # type: ignore[misc, assignment]


class FunctionaryInline(LegacyFunctionaryPermissionMixin, TabularInline):
    legacy_model_name = 'functionary'
    model = Functionary
    fk_name = 'functionary_role'
    extra = 1
    autocomplete_fields = ('member',)
    fields = ('member', 'name', 'year')
    ordering = ('-year', 'name')


@admin.register(Functionary)
class FunctionaryAdmin(LegacyFunctionaryPermissionMixin, ModelAdmin):
    legacy_model_name = 'functionary'
    list_display = ('get_display_name', 'functionary_role_link', 'year')
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

    @admin.display(description=_('Funktionärspost'))
    def functionary_role_link(self, obj):
        return format_html(
            '<a href="{}">{}</a>',
            reverse('admin:functionaries_functionaryrole_change', args=[obj.functionary_role_id]),
            obj.functionary_role,
        )


@admin.register(FunctionaryRole)
class FunctionaryRoleAdmin(
    LegacyFunctionaryPermissionMixin,
    ExtraChangeListLinksMixin,
    TranslationCompletionAdminMixin,
    FunctionaryRoleTranslationAdminBase,
):
    legacy_model_name = 'functionaryrole'
    changelist_links = (
        AdminLink(
            _('All assignments'),
            icon='manage_accounts',
            url_name='admin:functionaries_functionary_changelist',
            any_permissions=('functionaries.view_functionary', 'members.view_functionary'),
        ),
    )
    save_on_top = True
    list_display = ('title', 'translation_status', 'board', 'functionary_count')
    list_filter = ('board',)
    search_fields = ('title', 'functionary__name', 'functionary__member__first_name', 'functionary__member__last_name')
    ordering = ['title']
    inlines = [FunctionaryInline]

    def get_list_display(self, request):
        list_display = list(super().get_list_display(request))
        if not hasattr(request, 'user'):
            return list_display
        assignment_admin = self.admin_site._registry[Functionary]
        if not assignment_admin.has_view_permission(request):
            list_display.remove('functionary_count')
        return list_display

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(functionary_total=Count('functionary', distinct=True))

    @admin.display(description=_('Funktionärer'))
    def functionary_count(self, obj):
        count = getattr(obj, 'functionary_total', obj.functionary_set.count())
        if not count:
            return '0'
        return format_html(
            '<a href="{}?{}">{} {}</a>',
            reverse('admin:functionaries_functionary_changelist'),
            urlencode({'functionary_role__id__exact': obj.pk}),
            count,
            ngettext('functionary', 'functionaries', count),
        )
