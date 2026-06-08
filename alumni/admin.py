from django.contrib import admin

from alumni.models import AlumniEmailRecipient


@admin.register(AlumniEmailRecipient)
class AlumniEmailRecipientAdmin(admin.ModelAdmin):
    list_display = ("recipient_email",)
    search_fields = ("recipient_email",)
