from django.contrib import admin
from django.utils.safestring import mark_safe
from .models import Collection, Picture
from .forms import PictureAdminForm

admin.site.register(Picture)


class PicturesInline(admin.TabularInline):
    model = Picture
    fk_name = 'collection'
    can_delete = True
    readonly_fields = ('preview_image',)
    extra = 0

    def preview_image(self, obj):
        return mark_safe("""<img src="%s" style="width: auto; height: 80px"/> """ % obj.image.url)


@admin.register(Collection)
class CollectionAdmin(admin.ModelAdmin):
    actions_on_top = ['clean_media']
    save_on_top = True
    form = PictureAdminForm
    inlines = [
        PicturesInline,
    ]
    change_list_template = 'admin/archive/collection/change_list.html'

