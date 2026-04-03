from django import forms
from django.contrib import admin
from .models import Candidate


class CandidateAdminForm(forms.ModelForm):
    img_url = forms.URLField(required=False, assume_scheme="https")
    poll_url = forms.URLField(assume_scheme="https")

    class Meta:
        model = Candidate
        fields = "__all__"


@admin.register(Candidate)
class CandidateAdmin(admin.ModelAdmin):
    form = CandidateAdminForm
