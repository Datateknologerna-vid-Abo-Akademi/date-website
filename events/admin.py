import logging

from admin_ordering.admin import OrderableAdmin
from django.contrib import admin
from django.db.models import JSONField
from django.db.models import TextField
from django.template.response import TemplateResponse
from django_ckeditor_5.widgets import CKEditor5Widget
from django.urls import reverse, re_path
from django.utils.html import format_html
from modeltranslation.admin import TranslationAdmin
from modeltranslation.admin import TranslationTabularInline

from events import forms
from events.models import Event, EventAttendees, EventRegistrationForm
from .widgets import PrettyJSONWidget

logger = logging.getLogger('date')


class EventRegistrationFormInline(OrderableAdmin, admin.TabularInline):
    line_numbering = 0
    model = EventRegistrationForm
    fk_name = 'event'
    extra = 0
    fields = ('choice_number', 'name', 'type', 'required',
              'public_info', 'hide_for_avec', 'choice_list')
    can_delete = True
    ordering_field = ('choice_number',)
    ordering = ['choice_number']
    ordering_field_hide_input = True


class EventAttendeesFormInline(OrderableAdmin, admin.TabularInline):
    ordering_field = 'attendee_nr'
    ordering_field_hide_input = True
    model = EventAttendees
    fk_name = 'event'
    extra = 0
    list_editable = ('user', 'email', 'preferences', 'preferences')
    formfield_overrides = {
        JSONField: {'widget': PrettyJSONWidget(attrs={'initial': 'parsed'})}
    }
    can_delete = True
    ordering = ['attendee_nr']

    def get_fields(self, request, event):
        fields = ['attendee_nr', 'user', 'email',
                  'anonymous', 'preferences', 'time_registered']
        if event and event.sign_up_avec:
            fields.append('avec_for')
        return fields

    def get_readonly_fields(self, request, event):
        readonly_fields = ['time_registered']
        return readonly_fields

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        event_id = request.resolver_match.kwargs.get('object_id')
        if db_field.name == "avec_for":
            kwargs["queryset"] = EventAttendees.objects.filter(event=event_id)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


# TODO: Get it working with the old EventAdmin code that is commented out below
# TODO: Improve the admin panel UI for the translatable fields
# SEE https://django-modeltranslation.readthedocs.io/en/latest/admin.html
@admin.register(Event)
class EventAdmin(TranslationAdmin):
    list_display = (
        'title', 'created_time', 'event_date_start', 'published', 'get_attendee_count')
    ordering = ['-event_date_start']
    search_fields = ('title', 'author__first_name', 'created_time')
    inlines = [
        EventRegistrationFormInline,
        EventAttendeesFormInline]

    def get_attendee_count(self, obj):
        return obj.get_registrations().count()

    get_attendee_count.short_description = 'Anmälda'

# @admin.register(Event)
# class EventAdmin(admin.ModelAdmin):
#     save_on_top = True
#     list_display = (
#         'get_attendee_count', 'sign_up_max_participants',
#         'account_actions')
#     search_fields = ('title', 'author__first_name', 'created_time')
#     ordering = ['-event_date_start']

#     form = forms.EventCreationForm

#     inlines = [
#         EventRegistrationFormInline,
#         EventAttendeesFormInline
#     ]
    # class Media:
    #     js = ('core/js/eventform.js',)
    # 
    # def get_attendee_count(self, obj):
    #     return obj.get_registrations().count()
#     def get_urls(self):
#         urls = super().get_urls()
#         custom_urls = [
#             re_path(
#                 r'^(?P<event_id>.+)/list/$',
#                 self.admin_site.admin_view(self.process_list),
#                 name="registration_list"
#             ),
#         ]
#         return custom_urls + urls
#     def account_actions(self, obj):
#         return format_html(
#             '<a class="button" href="{}">Deltagarlista</a>&nbsp;',
#             reverse('admin:registration_list', args=[obj.pk])
#         )
#     account_actions.short_description = 'Deltagarlista'
#     account_actions.allow_tags = True
#     def process_list(self, request, event_id, *args, **kwargs):
#         context = self.admin_site.each_context(request)
#         event = self.get_object(request, event_id)
#         context['event'] = event
#         rf = event.get_registration_form()
#         context["form"] = [x.name for x in rf][::-1] if rf else None
#         return TemplateResponse(
#             request,
#             'events/list.html',
#             context
#         )

#     def get_attendee_count(self, obj):
#         return obj.get_registrations().count()

#     get_attendee_count.short_description = 'Anmälda'

#     def add_view(self, request, form_url='', extra_context=None):
#         self.fields = forms.EventCreationForm.Meta.fields
#         return super(EventAdmin, self).add_view(request, form_url, extra_context)

#     def change_view(self, request, object_id, form_url='', extra_context=None):
#         self.fields = forms.EventEditForm.Meta.fields
#         return super(EventAdmin, self).change_view(request, object_id, form_url, extra_context)

#     def get_form(self, request, obj=None, change=False, **kwargs):
#         if obj is None:
#             form = forms.EventCreationForm
#         else:
#             form = forms.EventEditForm

#         form.user = request.user
#         return form
#   formfield_overrides = {
#   TextField: {'widget': CKEditor5Widget},
#   }
