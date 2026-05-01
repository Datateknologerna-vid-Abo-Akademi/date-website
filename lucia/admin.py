from django import forms
from django.contrib import admin
from core.admin_base import ModelAdmin, PublicUrlAdminMixin, UnfoldFormMixin
from .models import Candidate


class CandidateAdminForm(UnfoldFormMixin, forms.ModelForm):
    img_url = forms.URLField(required=False, assume_scheme="https")
    poll_url = forms.URLField(assume_scheme="https")

    class Meta:
        model = Candidate
        fields = "__all__"


@admin.register(Candidate)
class CandidateAdmin(PublicUrlAdminMixin, ModelAdmin):
    form = CandidateAdminForm
    list_display = ('title', 'published')
    list_filter = ('published',)
    search_fields = ('title', 'slug', 'poll_url', 'img_url')
    prepopulated_fields = {'slug': ('title',)}
