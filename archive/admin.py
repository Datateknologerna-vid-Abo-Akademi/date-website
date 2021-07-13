from django.contrib import admin
from django.utils.safestring import mark_safe
from django.conf import settings

from .forms import DocumentAdminForm, PictureAdminForm, PublicAdminForm
from .models import Document, DocumentCollection, Picture, PictureCollection, PublicFile, PublicCollection


class PicturesInline(admin.TabularInline):
    model = Picture
    fk_name = 'collection'
    can_delete = True
    readonly_fields = ('preview_image',)
    extra = 0

    def preview_image(self, obj):
        return mark_safe("""<img src="%s" style="width: auto; height: 80px"/> """ % obj.image.url)


class DocumentInline(admin.TabularInline):
    model = Document
    fk_name = 'collection'
    can_delete = True
    extra = 1

class PublicFileInline(admin.TabularInline):
    model = PublicFile
    fk_name = 'collection'
    can_delete = True
    readonly_fields = ('preview_image',)
    extra = 1

    def preview_image(self, obj):
        return mark_safe("""<img src="%s" style="width: auto; height: 80px"/> """ % obj.some_file.url)


@admin.register(PictureCollection)
class PictureCollectionAdmin(admin.ModelAdmin):
    model = PictureCollection
    save_on_top = True
    form = PictureAdminForm
    inlines = [
        PicturesInline
    ]
    list_display = ('title', 'pub_date')

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.filter(type='Pictures')

    def get_changeform_initial_data(self, request):
        return {'type': 'Pictures'}


@admin.register(DocumentCollection)
class DocumentCollectionAdmin(admin.ModelAdmin):
    model = DocumentCollection
    save_on_top = True
    form = DocumentAdminForm
    inlines = [
        DocumentInline
    ]
    list_display = ('title', 'pub_date')

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.filter(type='Documents')

    def get_changeform_initial_data(self, request):
        return {'type': 'Documents'}


if settings.USE_S3:
    @admin.register(PublicCollection)
    class PublicCollectionAdmin(admin.ModelAdmin):
        model = PublicCollection
        save_on_top = True
        form = PublicAdminForm
        inlines = [
            PublicFileInline
        ]

        def get_queryset(self, request):
            qs = super().get_queryset(request)
            return qs.filter(type='PublicFiles')

        def get_changeform_initial_data(self, request):
            return {'type': 'PublicFiles'}
