import logging

# Translation and Ordering imports
from admin_ordering.admin import OrderableAdmin
from django.conf import settings
from django.contrib import admin, messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Count, IntegerField, JSONField, OuterRef, Subquery, TextField, Value
from django.db.models.functions import Coalesce
from django.forms import ModelForm
from django.forms.models import BaseInlineFormSet
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404, render
from django.template.response import TemplateResponse
from django.urls import re_path, reverse
from django.utils.html import format_html
from django.utils.timezone import now
from django.utils.translation import gettext_lazy as _
from django_ckeditor_5.widgets import CKEditor5Widget

from core.admin import (
    ActiveLanguageTranslationAdminMixin,
    LanguageTabbedTranslationAdmin,
    TranslationCompletionAdminMixin,
)
from core.admin_base import UNFOLD_FORMFIELD_OVERRIDES, ModelAdmin, PublicUrlAdminMixin, TabularInline
from core.admin_widgets import FLATPICKR_ADMIN_CSS, FLATPICKR_ADMIN_JS
from events import forms
from events.models import Event, EventAttendees, EventRegistrationForm, registration_terms_feature_enabled

from .widgets import PrettyJSONWidget

logger = logging.getLogger('date')

if settings.ENABLE_LANGUAGE_FEATURES:  # type: ignore[misc]
    from modeltranslation.admin import TranslationTabularInline

    # MRO when USE_UNFOLD=True: Mixin → Translation → unfold.TabularInline → admin.TabularInline
    # unfold sits between modeltranslation and Django's base so both layers get their super() calls.
    class EventTranslationInlineBase(ActiveLanguageTranslationAdminMixin, TranslationTabularInline, TabularInline):
        pass

    class EventTranslationAdminBase(ActiveLanguageTranslationAdminMixin, LanguageTabbedTranslationAdmin, ModelAdmin):
        pass
else:
    EventTranslationInlineBase = TabularInline  # type: ignore[misc, assignment]
    EventTranslationAdminBase = ModelAdmin  # type: ignore[misc, assignment]


class AvecAwareMixin:
    def _event_uses_avec(self, event):
        return bool(event and event.sign_up_avec)


class EventRegistrationFormSet(BaseInlineFormSet):
    def clean(self):
        super().clean()
        forms_by_name = {}
        for form in self.forms:
            if not hasattr(form, 'cleaned_data') or form.cleaned_data.get('DELETE'):
                continue
            name = (form.cleaned_data.get('name') or '').strip()
            forms_by_name.setdefault(name, []).append(form)

        for duplicate_forms in forms_by_name.values():
            if len(duplicate_forms) > 1 and any(
                form.instance._state.adding or 'name' in form.changed_data for form in duplicate_forms
            ):
                raise ValidationError(_('Fältnamnen måste vara unika inom evenemanget.'))


class EventRegistrationFormInline(AvecAwareMixin, OrderableAdmin, EventTranslationInlineBase):
    line_numbering = 0
    model = EventRegistrationForm
    formset = EventRegistrationFormSet
    fk_name = 'event'
    extra = 0
    can_delete = True
    ordering_field = 'choice_number'
    ordering = ['choice_number']
    ordering_field_hide_input = True

    def get_fields(self, request, event=None):
        fields = ['choice_number', 'name', 'type', 'required', 'public_info']
        if self._event_uses_avec(event):
            fields.append('hide_for_avec')
        fields.append('choice_list')
        return fields

    def get_fieldsets(self, request, event=None):
        return [(None, {'fields': self.get_fields(request, event)})]

    def get_formset(self, request, obj=None, **kwargs):
        if not self._event_uses_avec(obj):
            kwargs.setdefault('exclude', [])
            kwargs['exclude'] = [*kwargs['exclude'], 'hide_for_avec']
        return super().get_formset(request, obj, **kwargs)


class EventAttendeesForm(ModelForm):
    class Meta:
        model = EventAttendees
        fields = ['event', 'attendee_nr', 'user', 'email', 'preferences', 'anonymous', 'avec_for', 'original_event']

    def _get_validation_exclusions(self):
        exclude = super()._get_validation_exclusions()
        # The (event, attendee_nr) unique constraint is validated against the
        # database state as it is *before* the formset saves, which still
        # holds the pre-reorder numbers while a drag-and-drop reorder is
        # being submitted, so every moved row would look like a duplicate.
        # Skip the constraint here; EventAttendeesInlineFormSet renumbers in
        # one atomic pass and the database constraint still guards the final
        # state. The (event, email) unique_together check stays active, and
        # the positive integer range is still enforced by the database column.
        exclude.add('attendee_nr')
        return exclude


class EventAttendeesInlineFormSet(BaseInlineFormSet):
    def save(self, commit=True):
        # The admin_ordering drag reorder writes the final attendee_nr values
        # (10, 20, ...) into the forms in original row order, so a drag can
        # assign a number that another row still holds, violating the
        # (event, attendee_nr) unique constraint mid-save. Move every
        # existing row of the event to a non-conflicting band (5, 15, 25,
        # ...) first; the per-row saves then write the final values without
        # ever colliding. Rows whose forms did not change are restored
        # afterwards, because Django skips saving unchanged forms.
        self._shifted = False
        if commit and self._attendee_nr_reordered():
            self._shift_attendee_nrs()
        result = super().save(commit=commit)
        if commit and self._shifted:
            self._restore_unchanged_attendee_nrs()
        return result

    def _attendee_nr_reordered(self):
        if not self.instance.pk:
            return False
        return any('attendee_nr' in form.changed_data for form in self.forms)

    def _shift_attendee_nrs(self):
        # Band values are k*10+5: never a multiple of 10, so they cannot
        # collide with real or final values (all multiples of 10), and they
        # stay within the positive integer range for any practical event.
        rows = list(
            EventAttendees.objects.filter(event=self.instance)
            .order_by('attendee_nr', 'pk')
            .values_list('pk', 'attendee_nr')
        )
        self._original_nrs = {pk: nr for pk, nr in rows}
        for index, (pk, _nr) in enumerate(rows):
            EventAttendees.objects.filter(pk=pk).update(attendee_nr=index * 10 + 5)
        self._shifted = True

    def _restore_unchanged_attendee_nrs(self):
        saved_pks = {obj.pk for obj, _changed_data in self.changed_objects}
        for pk, nr in self._original_nrs.items():
            if pk not in saved_pks:
                EventAttendees.objects.filter(pk=pk).update(attendee_nr=nr)


class EventAttendeesFormInline(AvecAwareMixin, OrderableAdmin, EventTranslationInlineBase):
    ordering_field = 'attendee_nr'
    ordering_field_hide_input = True
    model = EventAttendees
    form = EventAttendeesForm
    formset = EventAttendeesInlineFormSet
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
        fields = ['attendee_nr', 'user', 'email', 'anonymous', 'preferences', 'time_registered']
        if event and event.children.exists():
            fields.append('original_event')
        if self._event_uses_avec(event):
            fields.append('avec_for')
        return fields

    def get_fieldsets(self, request, event=None):
        return [(None, {'fields': self.get_fields(request, event)})]

    def get_readonly_fields(self, request, event=None):
        readonly_fields = ['time_registered']
        if event and event.children.exists():
            readonly_fields.append('original_event')
        return readonly_fields

    def get_formset(self, request, obj=None, **kwargs):
        # Note: the exclude list passed via kwargs ends up overriding the
        # readonly-field exclusion Django computes in
        # InlineModelAdmin.get_formset (the kwargs dict is applied after the
        # defaults). Include readonly fields here explicitly, otherwise they
        # stay on the form as required fields and any save fails validation.
        exclude = [*kwargs.get('exclude', []), *self.get_readonly_fields(request, obj)]
        if not self._event_uses_avec(obj):
            exclude.append('avec_for')
        kwargs['exclude'] = exclude
        return super().get_formset(request, obj, **kwargs)

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
    formfield_overrides = {
        **UNFOLD_FORMFIELD_OVERRIDES,
        JSONField: {'widget': PrettyJSONWidget(attrs={'initial': 'parsed'})},
    }


class EventPublicationFilter(admin.SimpleListFilter):
    title = _('publicering')
    parameter_name = 'publication'

    def lookups(self, request, model_admin):
        return (
            ('published', _('Publicerad')),
            ('scheduled', _('Schemalagd')),
            ('hidden', _('Dold')),
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


# TODO: Get it working with the old EventAdmin code that is commented out below
# TODO: Improve the admin panel UI for the translatable fields
# SEE https://django-modeltranslation.readthedocs.io/en/latest/admin.html
@admin.register(Event)
class EventAdmin(PublicUrlAdminMixin, TranslationCompletionAdminMixin, EventTranslationAdminBase):
    save_on_top = True
    formfield_overrides = {
        **UNFOLD_FORMFIELD_OVERRIDES,
        TextField: {'widget': CKEditor5Widget},
    }
    list_display = (
        'title',
        'translation_status',
        'created_time',
        'event_date_start',
        'get_attendee_count',
        'sign_up_max_participants',
        'publication_status',
        'published_time',
        'account_actions',
        'parent',
    )
    search_fields = ('title', 'slug', 'author__first_name', 'author__last_name', 'author__username', 'author__email')
    list_filter = (EventPublicationFilter, 'sign_up', 'members_only')
    autocomplete_fields = ('author', 'parent')
    list_select_related = ('author', 'parent')
    ordering = ['-event_date_start']
    date_hierarchy = 'event_date_start'
    actions = ['delete_participants']

    form = forms.EventCreationForm

    inlines = [EventRegistrationFormInline, EventAttendeesFormInline]

    def get_list_display(self, request):
        list_display = list(super().get_list_display(request))
        if not hasattr(request, 'user'):
            return list_display
        attendee_admin = self.admin_site._registry[EventAttendees]
        if not attendee_admin.has_view_permission(request):
            list_display.remove('get_attendee_count')
            list_display.remove('account_actions')
        return list_display

    def get_queryset(self, request):
        attendee_sq = (
            EventAttendees.objects.filter(event=OuterRef('pk'))
            .order_by()
            .values('event')
            .annotate(cnt=Count('pk'))
            .values('cnt')
        )
        original_sq = (
            EventAttendees.objects.filter(original_event=OuterRef('pk'))
            .order_by()
            .values('original_event')
            .annotate(cnt=Count('pk'))
            .values('cnt')
        )
        return (
            super()
            .get_queryset(request)
            .select_related('author', 'parent')
            .annotate(
                _attendee_count=Coalesce(Subquery(attendee_sq, output_field=IntegerField()), Value(0)),
                _original_event_attendee_count=Coalesce(Subquery(original_sq, output_field=IntegerField()), Value(0)),
            )
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
                r'^(?P<event_id>.+)/list/$', self.admin_site.admin_view(self.process_list), name="registration_list"
            ),
        ]
        return custom_urls + urls

    @admin.display(description="Deltagarlista")
    def account_actions(self, obj):
        return format_html(
            '<a class="button admin-inline-action" href="{}">Deltagarlista</a>&nbsp;',
            reverse('admin:registration_list', args=[obj.pk]),
        )

    def has_delete_attendees_permission(self, request):
        attendee_admin = self.admin_site._registry[EventAttendees]
        return attendee_admin.has_delete_permission(request)

    @admin.action(
        description="Delete all attendees for selected events",
        permissions=['delete_attendees'],
    )
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
        attendee_admin = self.admin_site._registry[EventAttendees]
        if not self.has_view_permission(request) or not attendee_admin.has_view_permission(request):
            raise PermissionDenied

        context = self.admin_site.each_context(request)
        event = get_object_or_404(self.get_queryset(request), pk=event_id)
        context['event'] = event
        context['attendees'] = event.get_registrations()
        rf = event.get_registration_form()
        context["form"] = [x.name for x in rf][::-1] if rf else None
        return TemplateResponse(request, 'events/list.html', context)

    class Media:
        css = {'all': FLATPICKR_ADMIN_CSS}
        js = ('admin/js/jquery.init.js',) + FLATPICKR_ADMIN_JS + ('core/js/eventform.js',)

    @admin.display(description="Anmälda")
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

    @admin.display(description=_("Publicering"), ordering="published_time")
    def publication_status(self, obj):
        if obj.published_time is None:
            return _('Dold')
        if obj.published_time > now():
            return _('Schemalagd')
        return _('Publicerad')

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
