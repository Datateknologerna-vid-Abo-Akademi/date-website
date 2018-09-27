from django.contrib import admin
from django.urls import reverse
from django.utils.encoding import force_text
from django.utils.html import format_html
from django.utils.translation import ugettext_lazy as _

from .models import Collection, Picture


admin.site.register(Picture)


@admin.register(Collection)
class CollectionAdmin(admin.ModelAdmin):
    save_on_top = True
    fields = ['title', 'type', 'pub_date']
