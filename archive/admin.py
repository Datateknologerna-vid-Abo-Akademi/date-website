from django.contrib import admin
from django.utils.safestring import mark_safe
from .models import Collection, Picture

admin.site.register(Picture)


class PicturesInline(admin.TabularInline):
    model = Picture
    fk_name = 'collection'
    can_delete = True
    readonly_fields = ('preview_image',)

    def preview_image(self, obj):
        return mark_safe("""<img src="%s" style="width: 120px; height: 100px"/> """ % obj.image.url)


@admin.register(Collection)
class CollectionAdmin(admin.ModelAdmin):
    save_on_top = True
    fields = ['title', 'type', 'pub_date']
    inlines = [
        PicturesInline,
    ]
