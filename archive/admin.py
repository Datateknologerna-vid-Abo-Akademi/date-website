from django.contrib import admin
from django.utils.safestring import mark_safe
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from core.admin_base import ExtraChangeListLinksMixin, ModelAdmin, TabularInline
from core.admin_ui import AdminLink

from .forms import DocumentAdminForm, PictureAdminForm, PublicAdminForm
from .models import Document, DocumentCollection, Picture, PictureCollection, PublicFile, PublicCollection, ExamCollection


class ArchiveCollectionAdminMixin(ExtraChangeListLinksMixin):
    changelist_links = (
        AdminLink(_('Städa upp media'), icon='cleaning_services', url_name='archive:cleanMedia'),
    )


class PicturesInline(TabularInline):
    model = Picture
    fk_name = 'collection'
    can_delete = True
    readonly_fields = ('preview_image',)
    extra = 0

    def preview_image(self, obj):
        return mark_safe("""<img src="%s" style="width: auto; height: 80px"/> """ % obj.image.url)


class DocumentInline(TabularInline):
    model = Document
    fk_name = 'collection'
    can_delete = True
    extra = 1

class PublicFileInline(TabularInline):
    model = PublicFile
    fk_name = 'collection'
    can_delete = True
    readonly_fields = ('preview_image',)
    extra = 1

    def preview_image(self, obj):
        return mark_safe("""<img src="%s" style="width: auto; height: 80px"/> """ % obj.some_file.url)


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
