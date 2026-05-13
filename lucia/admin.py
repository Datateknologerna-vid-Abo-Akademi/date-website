from django import forms
from django.contrib import admin
from django.utils.timezone import now
from django.utils.translation import gettext_lazy as _
from core.admin_base import ModelAdmin, PublicUrlAdminMixin, UnfoldFormMixin
from core.admin_widgets import (
    FLATPICKR_ADMIN_CSS,
    FLATPICKR_ADMIN_JS,
    flatpickr_datetime_field,
)
from .models import Candidate


class CandidateAdminForm(UnfoldFormMixin, forms.ModelForm):
    img_url = forms.URLField(required=False, assume_scheme="https")
    poll_url = forms.URLField(assume_scheme="https")
    published_time = flatpickr_datetime_field(initial=now, required=False)

    class Meta:
        model = Candidate
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if 'published_time' in self.fields:
            self.fields['published_time'].help_text = _("Leave blank to keep the candidate hidden.")


class CandidatePublicationFilter(admin.SimpleListFilter):
    title = 'publicering'
    parameter_name = 'publication'

    def lookups(self, request, model_admin):
        return (
            ('published', 'Publicerad'),
            ('scheduled', 'Schemalagd'),
            ('hidden', 'Dold'),
        )

    def queryset(self, request, queryset):
        current_time = now()
        if self.value() == 'published':
            return queryset.filter(published_time__isnull=False, published_time__lte=current_time)
        if self.value() == 'scheduled':
            return queryset.filter(published_time__gt=current_time)
        if self.value() == 'hidden':
            return queryset.filter(published_time__isnull=True)
        return queryset


@admin.register(Candidate)
class CandidateAdmin(PublicUrlAdminMixin, ModelAdmin):
    form = CandidateAdminForm
    list_display = ('title', 'publication_status', 'published_time')
    list_filter = (CandidatePublicationFilter,)
    search_fields = ('title', 'slug', 'poll_url', 'img_url')
    prepopulated_fields = {'slug': ('title',)}

    def publication_status(self, obj):
        if obj.published_time is None:
            return 'Dold'
        if obj.published_time > now():
            return 'Schemalagd'
        return 'Publicerad'

    publication_status.short_description = 'Publicering'
    publication_status.admin_order_field = 'published_time'

    class Media:
        css = {'all': FLATPICKR_ADMIN_CSS}
        js = ('admin/js/jquery.init.js',) + FLATPICKR_ADMIN_JS
