from django.contrib import admin

from core.admin_base import ModelAdmin

from .models import IgUrl


@admin.register(IgUrl)
class IgUrlAdmin(ModelAdmin):
    list_display = ("url", "shortcode")
    search_fields = ("url", "shortcode")
    ordering = ("url",)
