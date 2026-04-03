from django import forms
from django.contrib import admin

from .models import AdUrl


class AdUrlAdminForm(forms.ModelForm):
    ad_url = forms.URLField(assume_scheme="https")
    company_url = forms.URLField(required=False, assume_scheme="https")

    class Meta:
        model = AdUrl
        fields = "__all__"


@admin.register(AdUrl)
class AdUrlAdmin(admin.ModelAdmin):
    form = AdUrlAdminForm
