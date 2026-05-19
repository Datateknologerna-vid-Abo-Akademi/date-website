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

from .forms import AlbumAdminForm
from .models import Album, Photo

logger = logging.getLogger("date")


def safe_image_preview(image_field):
    if not image_field:
        return "-"
    try:
        return format_html('<img src="{}" style="width: auto; height: 80px"/>', image_field.url)
    except Exception as exc:
        logger.warning("Unable to resolve gallery image URL for %s: %s", image_field.name, exc)
        return image_field.name


class GalleryAdminMixin(ExtraChangeListLinksMixin):
    changelist_links = (AdminLink(_("Städa upp media"), icon="cleaning_services", url_name="archive:cleanMedia"),)


class PhotoInline(TabularInline):
    model = Photo
    fk_name = "album"
    can_delete = True
    readonly_fields = ("preview_image",)
    extra = 0
    formfield_overrides = {
        **UNFOLD_FORMFIELD_OVERRIDES,
        models.ImageField: {"widget": SafeAdminFileWidget},
    }

    def preview_image(self, obj):
        return safe_image_preview(obj.image)


@admin.register(Album)
class AlbumAdmin(FlatpickrDateTimeAdminMixin, GalleryAdminMixin, ModelAdmin):
    save_on_top = True
    form = AlbumAdminForm
    inlines = [PhotoInline]
    list_display = ("title", "pub_date", "hide_for_gulis")
    search_fields = ("title",)
    ordering = ("-pub_date",)
    date_hierarchy = "pub_date"
    flatpickr_datetime_fields = ("pub_date",)

    legacy_permission_map = {
        "view": "archive.view_picturecollection",
        "add": "archive.add_picturecollection",
        "change": "archive.change_picturecollection",
        "delete": "archive.delete_picturecollection",
    }

    def _has_legacy_permission(self, request, action):
        return request.user.has_perm(self.legacy_permission_map[action])

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
