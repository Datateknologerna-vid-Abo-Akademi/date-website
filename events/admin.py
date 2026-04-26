import logging
from django.http import HttpResponseRedirect
from django.contrib import messages
from django.contrib import admin
from django.conf import settings
from django.db.models import Count, IntegerField, JSONField, OuterRef, Subquery, TextField, Value
from django.db.models.functions import Coalesce
from django.shortcuts import render
from django.template.response import TemplateResponse
from django_ckeditor_5.widgets import CKEditor5Widget
from django.urls import reverse, re_path
from django.utils.html import format_html
from core.admin_base import ModelAdmin, PublicUrlAdminMixin, TabularInline, UNFOLD_FORMFIELD_OVERRIDES

# Translation and Ordering imports
from admin_ordering.admin import OrderableAdmin

from core.admin import ActiveLanguageTranslationAdminMixin
from events import forms
from events.models import Event, EventAttendees, EventRegistrationForm, registration_terms_feature_enabled
from .widgets import PrettyJSONWidget

logger = logging.getLogger('date')

if settings.ENABLE_LANGUAGE_FEATURES:
    from modeltranslation.admin import TabbedTranslationAdmin, TranslationTabularInline

    # MRO when USE_UNFOLD=True: Mixin → Translation → unfold.TabularInline → admin.TabularInline
    # unfold sits between modeltranslation and Django's base so both layers get their super() calls.
    class EventTranslationInlineBase(ActiveLanguageTranslationAdminMixin, TranslationTabularInline, TabularInline):
        pass

    # MRO when USE_UNFOLD=True: Mixin → TabbedTranslation → unfold.ModelAdmin → admin.ModelAdmin
    class EventTranslationAdminBase(ActiveLanguageTranslationAdminMixin, TabbedTranslationAdmin, ModelAdmin):
        pass
else:
    EventTranslationInlineBase = TabularInline
    EventTranslationAdminBase = ModelAdmin


class EventRegistrationFormInline(OrderableAdmin, EventTranslationInlineBase):
    line_numbering = 0
    model = EventRegistrationForm
    fk_name = 'event'
    extra = 0
    fields = ('choice_number', 'name', 'type', 'required',
              'public_info', 'hide_for_avec', 'choice_list')
    can_delete = True
    ordering_field = 'choice_number'
    ordering = ['choice_number']
    ordering_field_hide_input = True

class EventAttendeesFormInline(OrderableAdmin, EventTranslationInlineBase):
    ordering_field = 'attendee_nr'
    ordering_field_hide_input = True
    model = EventAttendees
    fk_name = 'event'
    extra = 0
    list_editable = ('user', 'email', 'preferences')
    formfield_overrides = {
        **UNFOLD_FORMFIELD_OVERRIDES,
        JSONField: {'widget': PrettyJSONWidget(attrs={'initial': 'parsed'})},
    }
    can_delete = True
    ordering = ['attendee_nr']

    def get_fields(self, request, event):
        fields = ['attendee_nr', 'user', 'email',
                  'anonymous', 'preferences', 'time_registered']
        if event and event.children.exists():
            fields.append('original_event')
        if event and event.sign_up_avec:
            fields.append('avec_for')
        return fields

    def get_readonly_fields(self, request, event):
        readonly_fields = ['time_registered']
        if event and event.children.exists():
            readonly_fields.append('original_event')
        return readonly_fields

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        event_id = request.resolver_match.kwargs.get('object_id')
        if db_field.name == "avec_for":
            kwargs["queryset"] = EventAttendees.objects.filter(event=event_id)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


@admin.register(EventAttendees)
class EventAttendeesAdmin(ModelAdmin):
    list_display = ('event', 'user', 'email', 'time_registered', 'anonymous', 'original_event')
    list_filter = ('anonymous', 'time_registered')
    search_fields = (
        'user',
        'email',
        'event__title',
        'event__slug',
        'original_event__title',
        'original_event__slug',
        'avec_for__user',
        'avec_for__email',
    )
    autocomplete_fields = ('event', 'original_event', 'avec_for')
    list_select_related = ('event', 'original_event', 'avec_for')
    ordering = ('-time_registered',)
    date_hierarchy = 'time_registered'


# TODO: Get it working with the old EventAdmin code that is commented out below
# TODO: Improve the admin panel UI for the translatable fields
# SEE https://django-modeltranslation.readthedocs.io/en/latest/admin.html
@admin.register(Event)
class EventAdmin(PublicUrlAdminMixin, EventTranslationAdminBase):
    save_on_top = True
    formfield_overrides = {
        **UNFOLD_FORMFIELD_OVERRIDES,
        TextField: {'widget': CKEditor5Widget},
    }
    list_display = (
        'title', 'created_time', 'event_date_start', 'get_attendee_count', 
        'sign_up_max_participants', 'published', 'account_actions', 'parent'
    )
    search_fields = ('title', 'slug', 'author__first_name', 'author__last_name', 'author__username', 'author__email')
    list_filter = ('published', 'sign_up', 'members_only')
    autocomplete_fields = ('author', 'parent')
    list_select_related = ('author', 'parent')
    ordering = ['-event_date_start']
    date_hierarchy = 'event_date_start'
    actions = ['delete_participants']

    form = forms.EventCreationForm

    inlines = [
        EventRegistrationFormInline,
        EventAttendeesFormInline
    ]

    def get_queryset(self, request):
        attendee_sq = (
            EventAttendees.objects
            .filter(event=OuterRef('pk'))
            .values('event')
            .annotate(cnt=Count('pk'))
            .values('cnt')
        )
        original_sq = (
            EventAttendees.objects
            .filter(original_event=OuterRef('pk'))
            .values('original_event')
            .annotate(cnt=Count('pk'))
            .values('cnt')
        )
        return super().get_queryset(request).select_related('author', 'parent').annotate(
            _attendee_count=Coalesce(Subquery(attendee_sq, output_field=IntegerField()), Value(0)),
            _original_event_attendee_count=Coalesce(Subquery(original_sq, output_field=IntegerField()), Value(0)),
        )

    def get_fields(self, request, obj=None):
        fields = list(super().get_fields(request, obj))
        if not registration_terms_feature_enabled() and "require_registration_terms" in fields:
            fields.remove("require_registration_terms")
        return fields

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            re_path(
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

    @admin.action(description="Delete all attendees for selected events")
    def delete_participants(self, request, queryset):
        queryset = queryset.prefetch_related('eventattendees_set')
        attendees_to_delete = []
        for event in queryset:
            attendees_to_delete.extend(event.eventattendees_set.all())

        if 'confirm' in request.POST:
            for attendee in attendees_to_delete:
                attendee.delete()
            messages.success(request, f"{len(attendees_to_delete)} attendees deleted.")
            return HttpResponseRedirect(request.get_full_path())

        context = {
            'events': queryset,
            'attendees': attendees_to_delete,
            'opts': self.model._meta,
            'action_checkbox_name': admin.helpers.ACTION_CHECKBOX_NAME,
        }
        return render(request, 'admin/events/delete_participants_confirmation.html', context)

    def process_list(self, request, event_id, *args, **kwargs):
        context = self.admin_site.each_context(request)
        event = self.get_object(request, event_id)
        context['event'] = event
        rf = event.get_registration_form()
        context["form"] = [x.name for x in rf][::-1] if rf else None
        return TemplateResponse(request, 'events/list.html', context)

    class Media:
        js = (
            'admin/js/jquery.init.js',
            'core/js/eventform.js',
        )

    def get_attendee_count(self, obj):
        if obj.parent:
            count = getattr(obj, '_original_event_attendee_count', None)
            if count is not None:
                return count
            return EventAttendees.objects.filter(original_event=obj).count()

        count = getattr(obj, '_attendee_count', None)
        if count is not None:
            return count
        return obj.get_registrations().count()

    get_attendee_count.short_description = 'Anmälda'

    def add_view(self, request, form_url='', extra_context=None):
        return super().add_view(request, form_url, extra_context)

    def change_view(self, request, object_id, form_url='', extra_context=None):
        return super().change_view(request, object_id, form_url, extra_context)

    def get_form(self, request, obj=None, change=False, **kwargs):
        if obj is None:
            kwargs['form'] = forms.EventCreationForm
        else:
            kwargs['form'] = forms.EventEditForm

        form = super().get_form(request, obj, change=change, **kwargs)
        form.user = request.user
        return form
