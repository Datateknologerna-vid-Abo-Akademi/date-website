from django.apps import apps
from django.conf import settings
from django.contrib import admin
from django.utils.timezone import now
from django.utils.translation import gettext_lazy as _

from core.admin import (
    ActiveLanguageTranslationAdminMixin,
    LanguageTabbedTranslationAdmin,
    TranslationCompletionAdminMixin,
)
from core.admin_base import ModelAdmin, TabularInline
from core.admin_widgets import (
    FLATPICKR_ADMIN_CSS,
    FLATPICKR_ADMIN_JS,
    FlatpickrDateTimeAdminMixin,
)

from .models import Choice, Question, Vote

# Every association installs `polls`, and only DaTe installs `attendance`
# (core/settings/date.py). The flag is read once here and guards both the inline
# and the changelist column below, because `Question.attendance_poll` does not
# exist on a site that has no attendance app.
ATTENDANCE_INSTALLED = apps.is_installed('attendance')

if settings.ENABLE_LANGUAGE_FEATURES:  # type: ignore[misc]
    from modeltranslation.admin import TranslationTabularInline

    # MRO when USE_UNFOLD=True: Mixin → Translation → unfold.TabularInline → admin.TabularInline
    class PollTranslationInlineBase(ActiveLanguageTranslationAdminMixin, TranslationTabularInline, TabularInline):
        pass

    class PollTranslationAdminBase(ActiveLanguageTranslationAdminMixin, LanguageTabbedTranslationAdmin, ModelAdmin):
        pass
else:
    PollTranslationInlineBase = TabularInline  # type: ignore[misc, assignment]
    PollTranslationAdminBase = ModelAdmin  # type: ignore[misc, assignment]


if ATTENDANCE_INSTALLED:
    # Imported lazily on purpose, like the booking import in date/views.py: this
    # module is imported for every association and only DaTe installs attendance.
    from attendance.models import AttendancePoll

    class AttendancePollInline(TabularInline):
        """Pick the meeting whose room a voter has to be in.

        The poll itself is the inline's parent, so Django fills that side in and
        the editor only chooses the meeting.
        """

        model = AttendancePoll
        verbose_name_plural = _('Närvarokrav')
        extra = 0
        max_num = 1


class ChoiceInline(PollTranslationInlineBase):
    model = Choice
    extra = 0
    readonly_fields = ['votes']


class VoteInline(TabularInline):
    model = Vote
    extra = 0
    readonly_fields = ['user']

    def has_add_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        if request.user.is_superuser:
            return True
        return False

    def full_name(self, obj):
        return obj.user.get_full_name()


def question_list_display(attendance_installed: bool) -> tuple[str, ...]:
    """The poll changelist columns, with the meeting column only where it exists.

    The six associations that install `polls` without `attendance` get a
    changelist without the column at all: `Question.attendance_poll` does not
    exist there, and an admin system check rejects a column that names it. The
    flag is a parameter rather than a module read so that both lists are
    testable from one settings module.
    """
    columns = [
        'question_text',
        'translation_status',
        'pub_date',
        'publication_status',
        'published_time',
    ]
    if attendance_installed:
        columns.append('attendance_event')
    return tuple(columns) + ('show_results', 'end_vote')


class QuestionPublicationFilter(admin.SimpleListFilter):
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


class QuestionAdmin(FlatpickrDateTimeAdminMixin, TranslationCompletionAdminMixin, PollTranslationAdminBase):
    fieldsets = [
        (
            None,
            {
                'fields': [
                    'question_text',
                    'voting_options',
                    'multiple_choice',
                    'required_multiple_choices',
                    'published_time',
                    'show_results',
                    'end_vote',
                ]
            },
        ),
    ]
    list_display = question_list_display(ATTENDANCE_INSTALLED)
    inlines = [ChoiceInline, VoteInline] + ([AttendancePollInline] if ATTENDANCE_INSTALLED else [])
    list_filter = [QuestionPublicationFilter, 'show_results', 'end_vote', 'multiple_choice']
    search_fields = ['question_text', 'choice__choice_text', 'vote__user__username', 'vote__user__email']
    ordering = ('-pub_date',)
    date_hierarchy = 'pub_date'

    @admin.display(description=_("Publicering"), ordering="published_time")
    def publication_status(self, obj):
        if obj.published_time is None:
            return _('Dold')
        if obj.published_time > now():
            return _('Schemalagd')
        return _('Publicerad')

    if ATTENDANCE_INSTALLED:

        @admin.display(description=_("Närvaroevenemang"))
        def attendance_event(self, obj):
            """The meeting the poll is attached to, or a dash when it is not."""
            attendance_poll = getattr(obj, 'attendance_poll', None)
            if attendance_poll is None:
                return '-'
            return attendance_poll.event

        def get_queryset(self, request):
            # select_related so the column costs one join rather than a query
            # per row, the way the attendance change log does it.
            return super().get_queryset(request).select_related('attendance_poll__event')

        @admin.display(description=_("Närvarande i mötet nu"))
        def attendance_present_now(self, obj):
            """How many the poll's meeting counts as present right now.

            ``present_count()`` rather than ``present_attendees()``: only the
            number is wanted here, and the count runs on every backend while the
            list's ``DISTINCT ON`` does not.
            """
            return obj.attendance_poll.event.present_count()

        @admin.display(description=_("Har röstat"))
        def attendance_voters(self, obj):
            """How many have voted so far, to read beside the headcount above."""
            return obj.voters.count()

        def get_readonly_fields(self, request, obj=None):
            readonly_fields = super().get_readonly_fields(request, obj)
            # An ordinary poll, and the add page where no attachment exists yet,
            # keep the page they had. The readouts are appended rather than set
            # in the class, because `Question.attendance_poll` does not exist at
            # all on an association without the attendance app.
            if obj is not None and getattr(obj, 'attendance_poll', None) is not None:
                return (*readonly_fields, 'attendance_present_now', 'attendance_voters')
            return readonly_fields

        def get_fieldsets(self, request, obj=None):
            fieldsets = list(super().get_fieldsets(request, obj))
            # A read-only field is rendered only when a fieldset names it, so the
            # attachment that adds the readouts to readonly_fields appends them
            # to the last section here. They are on the change page alone, never
            # in list_display, so no changelist row pays a query for them.
            if 'attendance_present_now' not in self.get_readonly_fields(request, obj):
                return fieldsets

            name, options = fieldsets[-1]
            fields = tuple(options.get('fields', ())) + ('attendance_present_now', 'attendance_voters')
            fieldsets[-1] = (name, {**options, 'fields': fields})
            return fieldsets

    class Media:
        css = {'all': FLATPICKR_ADMIN_CSS}
        js = ('admin/js/jquery.init.js',) + FLATPICKR_ADMIN_JS


admin.site.register(Question, QuestionAdmin)
