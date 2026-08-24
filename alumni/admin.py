from django.contrib import admin

from alumni.models import AlumniEmailRecipient
from core.admin_base import ModelAdmin


@admin.register(AlumniEmailRecipient)
class AlumniEmailRecipientAdmin(ModelAdmin):
    list_display = ("recipient_email",)
    search_fields = ("recipient_email",)
