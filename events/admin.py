import logging

from admin_ordering.admin import OrderableAdmin
from django.conf.urls import url
from django.contrib import admin
from django.contrib.postgres.fields import JSONField
from django.template.response import TemplateResponse
from django.urls import reverse
from django.utils.html import format_html

from events import forms
from events.models import Event, EventAttendees, EventRegistrationForm
from events.widgets import PrettyJSONWidget

logger = logging.getLogger('date')


class EventRegistrationFormInline(admin.TabularInline):
    line_numbering = 0
    model = EventRegistrationForm
    fk_name = 'event'
    extra = 0
    readonly_fields = ('line_number',)
    fields = ('line_number', 'name', 'type', 'required', 'public_info', 'choice_list')
    can_delete = True

    def line_number(self, obj):
        self.line_numbering += 1
        return self.line_numbering

    line_number.short_description = '#'


class EventAttendeesFormInline(OrderableAdmin, admin.TabularInline):
    ordering_field = 'attendee_nr'
    ordering_field_hide_input = True
    model = EventAttendees
    fk_name = 'event'
    extra = 0
    list_editable = ('user', 'email', 'preferences')
    readonly_fields = ('time_registered',)
    fields = ('attendee_nr', 'user', 'email', 'anonymous', 'preferences', 'time_registered')
    formfield_overrides = {
        JSONField: {'widget': PrettyJSONWidget()}
    }
    can_delete = True
    ordering = ['attendee_nr']


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    save_on_top = True
    list_display = (
        'title', 'created_time', 'event_date_start', 'get_attendee_count', 'sign_up_max_participants', 'published',
        'account_actions')
    search_fields = ('title', 'author', 'created_time')
    ordering = ['-event_date_start']

    form = forms.EventCreationForm

    inlines = [
        EventRegistrationFormInline,
        EventAttendeesFormInline
    ]

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            url(
                r'^(?P<event_id>.+)/list/$',
                self.admin_site.admin_view(self.process_list),
                name="registration_list"
            ),
        ]
        return custom_urls + urls

    def account_actions(self, obj):
        return format_html(
            '<a class="button" href="{}">Deltagarlista</a>&nbsp;',
            reverse('admin:registration_list', args=[obj.pk])
        )

    account_actions.short_description = 'Deltagarlista'
    account_actions.allow_tags = True

    def process_list(self, request, event_id, *args, **kwargs):
        context = self.admin_site.each_context(request)
        event = self.get_object(request, event_id)
        context['event'] = event
        return TemplateResponse(
            request,
            'events/list.html',
            context
        )

    class Media:
        js = ('js/eventform.js',)

    def get_attendee_count(self, obj):
        return obj.get_registrations().count()

    get_attendee_count.short_description = 'Anmälda'

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
