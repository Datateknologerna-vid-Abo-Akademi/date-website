from django.contrib import admin
from django.utils.translation import gettext_lazy as _

from core.admin_base import ModelAdmin

from .models import Post


@admin.register(Post)
class PostAdmin(ModelAdmin):
    list_display = ('pseudonym', 'content_preview', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('pseudonym', 'content')
    ordering = ('-created_at',)

    @admin.display(description=_("Meddelande"))
    def content_preview(self, obj):
        return obj.content[:80] + '...' if len(obj.content) > 80 else obj.content
