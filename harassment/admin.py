from django.contrib import admin

from core.admin_base import ModelAdmin

from .models import Harassment, HarassmentEmailRecipient


@admin.register(Harassment)
class HarassmentAdmin(ModelAdmin):
    list_display = ("email", "message_preview")
    search_fields = ("email", "message")

    @admin.display(description="Message")
    def message_preview(self, obj):
        return obj.message[:80] + "..." if len(obj.message) > 80 else obj.message


@admin.register(HarassmentEmailRecipient)
class HarassmentEmailRecipientAdmin(ModelAdmin):
    list_display = ("recipient_email",)
    search_fields = ("recipient_email",)
    ordering = ("recipient_email",)
