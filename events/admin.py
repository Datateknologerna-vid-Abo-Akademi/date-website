from events import forms
from django.contrib import admin

from events.models import Event


class EventAdmin(admin.ModelAdmin):

    list_display = ('title', 'created_time', 'event_date_start', 'published')
    search_fields = ('title', 'author', 'created_time')

    def add_view(self, request, form_url='', extra_context=None):
        self.fields = forms.EventCreationForm.Meta.fields
        return super(EventAdmin, self).add_view(request, form_url, extra_context)

    def change_view(self, request, object_id, form_url='', extra_context=None):
        self.fields = forms.EventEditForm.Meta.fields
        return super(EventAdmin, self).change_view(request, object_id, form_url, extra_context)

    def get_form(self, request, obj=None, change=False, **kwargs):
        if obj is None:
            form = forms.EventCreationForm
        else:
            form = forms.EventEditForm

        form.user = request.user
        return form


admin.site.register(Event, EventAdmin)
