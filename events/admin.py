from events import forms
from django.contrib import admin

from events.models import Event, EventRegistrationForm, EventAttendees

class EventRegistrationFormInline(admin.TabularInline):
    model = EventRegistrationForm
    fk_name = 'event'
    extra = 0
    fields = ('name', 'type', 'required', 'published', 'choice_list')
    can_delete = True

class EventAttendeesFormInline(admin.TabularInline):
    model = EventAttendees
    fk_name = 'event'
    extra = 0
    fields = ('user', 'time_registered')
    can_delete = True
    ordering = ['-time_registered']

class EventAdmin(admin.ModelAdmin):

    list_display = ('title', 'created_time', 'event_date_start', 'published')
    search_fields = ('title', 'author', 'created_time')
    ordering = ['-event_date_start']
    save_on_top = True
    inlines = [
        EventRegistrationFormInline,
        EventAttendeesFormInline
    ]

    class Media:
        js = ('js/eventform.js',)

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
