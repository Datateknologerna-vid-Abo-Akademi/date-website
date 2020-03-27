from django.contrib import admin
from django.utils.safestring import mark_safe
from .models import Picture, Document, DocumentCollection, PictureCollection
from .forms import PictureAdminForm, DocumentAdminForm


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


@admin.register(PictureCollection)
class PictureCollectionAdmin(admin.ModelAdmin):
    model = PictureCollection
    save_on_top = True
    form = PictureAdminForm
    inlines = [
        PicturesInline
    ]

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

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.filter(type='Documents')

    def get_changeform_initial_data(self, request):
        return {'type': 'Documents'}
