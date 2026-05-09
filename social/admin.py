from django.contrib import admin
from core.admin_base import ModelAdmin

from .models import Harassment, IgUrl, HarassmentEmailRecipient


@admin.register(IgUrl)
class IgUrlAdmin(ModelAdmin):
    list_display = ('url', 'shortcode')
    search_fields = ('url', 'shortcode')
    ordering = ('url',)


@admin.register(Harassment)
class HarassmentAdmin(ModelAdmin):
    list_display = ('email', 'message_preview')
    search_fields = ('email', 'message')

    def message_preview(self, obj):
        return obj.message[:80] + '…' if len(obj.message) > 80 else obj.message

    message_preview.short_description = 'Message'


@admin.register(HarassmentEmailRecipient)
class HarassmentEmailRecipientAdmin(ModelAdmin):
    list_display = ('recipient_email',)
    search_fields = ('recipient_email',)
    ordering = ('recipient_email',)
