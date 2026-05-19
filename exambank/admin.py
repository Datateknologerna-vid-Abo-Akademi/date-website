import logging

from django.contrib import admin
from django.db import models
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from core.admin_base import UNFOLD_FORMFIELD_OVERRIDES, ExtraChangeListLinksMixin, ModelAdmin, TabularInline
from core.admin_ui import AdminLink
from core.admin_widgets import (
    FLATPICKR_ADMIN_CSS,
    FLATPICKR_ADMIN_JS,
    FlatpickrDateTimeAdminMixin,
    SafeAdminFileWidget,
)

from .forms import ExamArchiveAdminForm, ExamBankAccessSettingsAdminForm
from .models import ExamArchive, ExamBankAccessSettings, ExamFile

logger = logging.getLogger("date")


def safe_file_link(file_field, label=None):
    if not file_field:
        return "-"
    label = label or file_field.name
    try:
        return format_html(
            '<a href="{}" target="_blank" rel="noopener noreferrer">{}</a>',
            file_field.url,
            label,
        )
    except Exception as exc:
        logger.warning("Unable to resolve exam file URL for %s: %s", file_field.name, exc)
        return label


class ExamBankAdminMixin(ExtraChangeListLinksMixin):
    changelist_links = (AdminLink(_("Städa upp media"), icon="cleaning_services", url_name="archive:cleanMedia"),)


class ExamFileInline(TabularInline):
    model = ExamFile
    fk_name = "archive"
    can_delete = True
    extra = 1
    formfield_overrides = {
        **UNFOLD_FORMFIELD_OVERRIDES,
        models.FileField: {"widget": SafeAdminFileWidget},
    }


@admin.register(ExamArchive)
class ExamArchiveAdmin(FlatpickrDateTimeAdminMixin, ExamBankAdminMixin, ModelAdmin):
    save_on_top = True
    form = ExamArchiveAdminForm
    inlines = [ExamFileInline]
    list_display = ("title", "pub_date", "hide_for_gulis")
    search_fields = ("title", "examfile__title")
    ordering = ("-pub_date",)
    date_hierarchy = "pub_date"
    flatpickr_datetime_fields = ("pub_date",)

    legacy_permission_map = {
        "view": "archive.view_examcollection",
        "add": "archive.add_examcollection",
        "change": "archive.change_examcollection",
        "delete": "archive.delete_examcollection",
    }

    def _has_legacy_permission(self, request, action):
        return request.user.has_perm(self.legacy_permission_map[action])

    def has_module_permission(self, request):
        if super().has_module_permission(request):
            return True
        return any(self._has_legacy_permission(request, action) for action in self.legacy_permission_map)

    def has_view_permission(self, request, obj=None):
        return super().has_view_permission(request, obj) or self._has_legacy_permission(request, "view")

    def has_add_permission(self, request):
        return super().has_add_permission(request) or self._has_legacy_permission(request, "add")

    def has_change_permission(self, request, obj=None):
        return super().has_change_permission(request, obj) or self._has_legacy_permission(request, "change")

    def has_delete_permission(self, request, obj=None):
        return super().has_delete_permission(request, obj) or self._has_legacy_permission(request, "delete")

    class Media:
        css = {"all": FLATPICKR_ADMIN_CSS}
        js = ("admin/js/jquery.init.js",) + FLATPICKR_ADMIN_JS


@admin.register(ExamBankAccessSettings)
class ExamBankAccessSettingsAdmin(ModelAdmin):
    form = ExamBankAccessSettingsAdminForm
    list_display = ("__str__", "require_sign_in", "password_configured")

    def has_add_permission(self, request):
        return not ExamBankAccessSettings.objects.exists() and super().has_add_permission(request)

    def has_delete_permission(self, request, obj=None):
        return False

    def password_configured(self, obj):
        return obj.has_password

    password_configured.boolean = True
    password_configured.short_description = _("Lösenord inställt")
