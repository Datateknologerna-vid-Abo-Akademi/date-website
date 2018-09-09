from django.contrib import admin
from django.urls import reverse
from django.utils.encoding import force_text
from django.utils.html import format_html
from django.utils.translation import ugettext_lazy as _

from .models import Collection, AbstractFile


def get_file_preview(obj):
    if obj.pk:  # if object has already been saved and has a primary key, show picture preview
        return format_html(
            u'<a href="{src}" target="_blank"><img src="{src}" alt="{title}" style="max-width: 200px; max-height: 200px;" /></a>',
            src=obj.file.url,
            title=obj.title)
    return _("(choose a picture and save and continue editing to see the preview)")


get_file_preview.allow_tags = True
get_file_preview.short_description = _("Picture Preview")


class FileInline(admin.StackedInline):
    model = AbstractFile
    extra = 0
    fields = ["get_edit_link", "title", "file", get_file_preview]
    readonly_fields = ["get_edit_link", get_file_preview]

    def get_edit_link(self, obj=None):
        if obj.pk:  # if object has already been saved and has a primary key, show link to it
            url = reverse('admin:%s_%s_change' % (obj._meta.app_label, obj._meta.model_name), args=[force_text(obj.pk)])
            return format_html(
                u'<a href="{url}">{text}</a>',
                url=url,
                text=_("Edit this %s separately") % obj._meta.verbose_name,
            )
        return _("(save and continue editing to create a link)")

    get_edit_link.short_description = _("Edit link")
    get_edit_link.allow_tags = True


@admin.register(Collection)
class CollectionAdmin(admin.ModelAdmin):
    save_on_top = True
    fields = ['title', 'pub_date']
    inlines = [FileInline]


@admin.register(AbstractFile)
class AbstractFileAdmin(admin.ModelAdmin):
    fields = ['collection', 'title', 'file', get_file_preview]
    readonly_fields = [get_file_preview]
