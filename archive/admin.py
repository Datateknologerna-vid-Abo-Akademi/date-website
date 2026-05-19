import logging

from django.conf import settings
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

from .forms import DocumentAdminForm, PublicAdminForm
from .models import Document, DocumentCollection, PublicCollection, PublicFile

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
        logger.warning("Unable to resolve archive file URL for %s: %s", file_field.name, exc)
        return label


class ArchiveCollectionAdminMixin(ExtraChangeListLinksMixin):
    changelist_links = (AdminLink(_("Städa upp media"), icon="cleaning_services", url_name="archive:cleanMedia"),)


class SafeFileInlineMixin:
    formfield_overrides = {
        **UNFOLD_FORMFIELD_OVERRIDES,
        models.FileField: {"widget": SafeAdminFileWidget},
        models.ImageField: {"widget": SafeAdminFileWidget},
    }


class DocumentInline(SafeFileInlineMixin, TabularInline):
    model = Document
    fk_name = "collection"
    can_delete = True
    extra = 1


class PublicFileInline(SafeFileInlineMixin, TabularInline):
    model = PublicFile
    fk_name = "collection"
    can_delete = True
    readonly_fields = ("preview_image",)
    extra = 1

    def preview_image(self, obj):
        return safe_file_link(obj.some_file)


@admin.register(DocumentCollection)
class DocumentCollectionAdmin(FlatpickrDateTimeAdminMixin, ArchiveCollectionAdminMixin, ModelAdmin):
    model = DocumentCollection
    save_on_top = True
    form = DocumentAdminForm
    inlines = [DocumentInline]
    list_display = ("title", "pub_date", "hide_for_gulis")
    search_fields = ("title", "document__title")
    ordering = ("-pub_date",)
    date_hierarchy = "pub_date"
    flatpickr_datetime_fields = ("pub_date",)

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.filter(type="Documents")

    def get_changeform_initial_data(self, request):
        return {"type": "Documents"}

    class Media:
        css = {"all": FLATPICKR_ADMIN_CSS}
        js = ("admin/js/jquery.init.js",) + FLATPICKR_ADMIN_JS


if settings.USE_S3:  # type: ignore[misc]

    @admin.register(PublicCollection)
    class PublicCollectionAdmin(FlatpickrDateTimeAdminMixin, ArchiveCollectionAdminMixin, ModelAdmin):
        model = PublicCollection
        save_on_top = True
        form = PublicAdminForm
        inlines = [PublicFileInline]
        list_display = ("title", "pub_date")
        search_fields = ("title",)
        ordering = ("-pub_date",)
        date_hierarchy = "pub_date"
        flatpickr_datetime_fields = ("pub_date",)

        def get_queryset(self, request):
            qs = super().get_queryset(request)
            return qs.filter(type="PublicFiles")

        def get_changeform_initial_data(self, request):
            return {"type": "PublicFiles"}

        class Media:
            css = {"all": FLATPICKR_ADMIN_CSS}
            js = ("admin/js/jquery.init.js",) + FLATPICKR_ADMIN_JS
