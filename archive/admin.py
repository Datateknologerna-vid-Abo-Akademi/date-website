import logging

from django.contrib import admin
from django.conf import settings
from django.db import models
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from core.admin_base import ExtraChangeListLinksMixin, ModelAdmin, TabularInline
from core.admin_widgets import SafeAdminFileWidget
from core.admin_ui import AdminLink

from .forms import DocumentAdminForm, PictureAdminForm, PublicAdminForm
from .models import Document, DocumentCollection, Picture, PictureCollection, PublicFile, PublicCollection, ExamCollection

logger = logging.getLogger('date')


def safe_file_link(file_field, label=None):
    if not file_field:
        return '-'
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


def safe_image_preview(image_field):
    if not image_field:
        return '-'
    try:
        return format_html('<img src="{}" style="width: auto; height: 80px"/>', image_field.url)
    except Exception as exc:
        logger.warning("Unable to resolve archive image URL for %s: %s", image_field.name, exc)
        return image_field.name


class ArchiveCollectionAdminMixin(ExtraChangeListLinksMixin):
    changelist_links = (
        AdminLink(_('Städa upp media'), icon='cleaning_services', url_name='archive:cleanMedia'),
    )


class SafeFileInlineMixin:
    formfield_overrides = {
        models.FileField: {'widget': SafeAdminFileWidget},
        models.ImageField: {'widget': SafeAdminFileWidget},
    }


class PicturesInline(SafeFileInlineMixin, TabularInline):
    model = Picture
    fk_name = 'collection'
    can_delete = True
    readonly_fields = ('preview_image',)
    extra = 0

    def preview_image(self, obj):
        return safe_image_preview(obj.image)


class DocumentInline(SafeFileInlineMixin, TabularInline):
    model = Document
    fk_name = 'collection'
    can_delete = True
    extra = 1

class PublicFileInline(SafeFileInlineMixin, TabularInline):
    model = PublicFile
    fk_name = 'collection'
    can_delete = True
    readonly_fields = ('preview_image',)
    extra = 1

    def preview_image(self, obj):
        return safe_file_link(obj.some_file)


@admin.register(PictureCollection)
class PictureCollectionAdmin(ArchiveCollectionAdminMixin, ModelAdmin):
    model = PictureCollection
    save_on_top = True
    form = PictureAdminForm
    inlines = [PicturesInline]
    list_display = ('title', 'pub_date', 'hide_for_gulis')
    search_fields = ('title',)
    ordering = ('-pub_date',)
    date_hierarchy = 'pub_date'

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.filter(type='Pictures')

    def get_changeform_initial_data(self, request):
        return {'type': 'Pictures'}


@admin.register(DocumentCollection)
class DocumentCollectionAdmin(ArchiveCollectionAdminMixin, ModelAdmin):
    model = DocumentCollection
    save_on_top = True
    form = DocumentAdminForm
    inlines = [DocumentInline]
    list_display = ('title', 'pub_date', 'hide_for_gulis')
    search_fields = ('title', 'document__title')
    ordering = ('-pub_date',)
    date_hierarchy = 'pub_date'

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.filter(type='Documents')

    def get_changeform_initial_data(self, request):
        return {'type': 'Documents'}


@admin.register(ExamCollection)
class ExamCollectionAdmin(ArchiveCollectionAdminMixin, ModelAdmin):
    model = ExamCollection
    save_on_top = True
    form = DocumentAdminForm
    inlines = [DocumentInline]
    list_display = ('title', 'pub_date', 'hide_for_gulis')
    search_fields = ('title', 'document__title')
    ordering = ('-pub_date',)
    date_hierarchy = 'pub_date'

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.filter(type='Exams')

    def get_changeform_initial_data(self, request):
        return {'type': 'Exams'}


if settings.USE_S3:
    @admin.register(PublicCollection)
    class PublicCollectionAdmin(ArchiveCollectionAdminMixin, ModelAdmin):
        model = PublicCollection
        save_on_top = True
        form = PublicAdminForm
        inlines = [PublicFileInline]
        list_display = ('title', 'pub_date')
        search_fields = ('title',)
        ordering = ('-pub_date',)
        date_hierarchy = 'pub_date'

        def get_queryset(self, request):
            qs = super().get_queryset(request)
            return qs.filter(type='PublicFiles')

        def get_changeform_initial_data(self, request):
            return {'type': 'PublicFiles'}
