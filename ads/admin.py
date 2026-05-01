from django import forms
from django.contrib import admin
from core.admin_base import ModelAdmin, UnfoldFormMixin

from .models import AdUrl


class AdUrlAdminForm(UnfoldFormMixin, forms.ModelForm):
    ad_url = forms.URLField(assume_scheme="https")
    company_url = forms.URLField(required=False, assume_scheme="https")

    class Meta:
        model = AdUrl
        fields = "__all__"


@admin.register(AdUrl)
class AdUrlAdmin(ModelAdmin):
    form = AdUrlAdminForm
    list_display = ('ad_url', 'company_url')
    search_fields = ('ad_url', 'company_url')
    ordering = ('ad_url',)
