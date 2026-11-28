import csv
from datetime import datetime
from typing import Any

from django import forms
from django.contrib import admin
from django.core.exceptions import PermissionDenied
from django.db.models import Count
from django.http import HttpRequest, HttpResponse, HttpResponseRedirect, QueryDict
from django.shortcuts import get_object_or_404, render
from django.urls import re_path, reverse
from django.utils.html import format_html
from django.utils.safestring import SafeString
from django.utils.timezone import localtime
from django.utils.translation import gettext_lazy as _
from django.utils.translation import pgettext_lazy

from core.admin_base import UNFOLD_FORMFIELD_OVERRIDES, ModelAdmin
from core.admin_widgets import (
    FLATPICKR_ADMIN_CSS,
    FLATPICKR_ADMIN_JS,
    FlatpickrDateTimeAdminMixin,
)
from members.models import Member

from . import models, websocket
from .models import AttendanceChange, AttendanceEvent

# The report's downloads are read in Excel by a Swedish association admin, where
# the comma is the decimal separator and the list separator is the semicolon.
# Deliberately not the csv module's default, and deliberately not what
# `billing/admin.py` does.
CSV_DELIMITER = ";"
# What makes Excel read the file as UTF-8 rather than as the local codepage,
# which would mangle every "å", "ä" and "ö" in a name.
UTF8_BOM = "\ufeff"

# How many rows of the meeting's timeline the report draws. The CSV carries every
# row, and a meeting with thousands of changes should not build a page with that
# many; this is high enough that an ordinary meeting is shown whole.
REPORT_TIMELINE_ROWS = 1000

TIMELINE_FIELDNAMES = (_("Tid"), _("Deltagare"), _("Ändring"), _("Typ"))
POLL_FIELDNAMES = (_("Fråga"), _("Val"), _("Röster"), _("Andel (%)"), _("Röstsedlar"), _("Röstande"))


def attendee_identity(change: AttendanceChange) -> tuple[str, int | None]:
    """The key that tells two attendees apart, the same one the overview page uses.

    A member and a guest are different tables, so their primary keys are not
    comparable and the kind has to be part of the identity.
    """
    if change.user_id is not None:
        return ("user", change.user_id)

    return ("non_member", change.non_member_id)


def peak_present_count(changes: list[AttendanceChange], end_datetime: datetime | None = None) -> int:
    """The largest headcount in the meeting, ignoring changes after a recorded end.

    The timeline is already loaded for the page, so replaying it in Python gives
    the same answer on every backend without another query. A meeting with no
    recorded end includes every change; a meeting with an end includes changes
    through that exact timestamp only.
    """
    present: set[tuple[str, int | None]] = set()
    peak = 0

    for change in changes:
        if end_datetime is not None and change.timestamp > end_datetime:
            continue

        key = attendee_identity(change)
        if change.type == AttendanceChange.Type.ENTER:
            present.add(key)
        else:
            # A departure for somebody who never arrived is not an error: it is
            # the same one-sided log the presence count tolerates.
            present.discard(key)
        peak = max(peak, len(present))

    return peak


def ever_present_count(changes: list[AttendanceChange]) -> int:
    """How many distinct attendees ever arrived, however often they came back."""
    return len({attendee_identity(change) for change in changes if change.type == AttendanceChange.Type.ENTER})


def present_at_end(event: AttendanceEvent) -> int:
    """How many were in the room at the meeting's end, or at its last change.

    A meeting that recorded an end time is read at that moment, so the answer is
    the same every time the report is opened. A meeting without one is read at
    its last recorded change rather than at the current time. With no changes,
    the answer is 0. Both list and count readers break timestamp ties by primary
    key, matching the order of the report timeline.
    """
    if event.end_datetime is not None:
        return event.present_count(event.end_datetime)

    latest = event.attendance_changes.order_by("-timestamp", "-pk").first()
    if latest is None:
        return 0

    return event.present_count(latest.timestamp)


def present_at_end_label(event: AttendanceEvent) -> str:
    """The report's honest label for its meeting-end or last-change headcount."""
    if event.end_datetime is not None:
        return str(_("Närvarande vid slutet"))
    return str(_("Närvarande vid sista ändringen"))


def change_action_label(change: AttendanceChange) -> str:
    """The arrival or departure in the reader's language.

    ``get_type_display()`` returns the ``gettext_noop`` source string rather than
    a translated one, so it has to be translated again, with the same context the
    event page's change log uses.
    """
    return str(pgettext_lazy("left/entered in general", change.get_type_display()))


def attendee_kind_label(change: AttendanceChange) -> str:
    """Whether this row is about a member or about a guest."""
    return str(_("Medlem") if change.user_id is not None else _("Icke-medlem"))


def local_timestamp(value: datetime) -> str:
    """The local date and time in one form that sorts and cannot be misread.

    The page shows the association's usual localized date and time; the CSV keeps
    the ISO order, because a spreadsheet column wants a value it can sort and a
    reader in Finland or Sweden reads ``2026-06-15 14:05`` without guessing.
    """
    return localtime(value).strftime("%Y-%m-%d %H:%M")


def report_filename(event: AttendanceEvent, prefix: str) -> str:
    """``<prefix>_<slug>_<YYYY-MM-DD>.csv``, named from the slug and the start date.

    The slug is ASCII by construction (``allow_unicode=False`` on the field),
    while the title is not, and a filename travels through mail clients and
    filesystems that a header value does not.
    """
    start = localtime(event.start_datetime).strftime("%Y-%m-%d")

    return f"{prefix}_{event.slug}_{start}.csv"


def sanitize_csv_string(value: Any) -> Any:
    """Neutralize Excel formula prefixes in string data cells, never in headers/numbers.

    CSV quoting protects delimiters and quotes, not spreadsheet formulas. A
    leading apostrophe makes formula-like values literal text when opened in
    Excel, including those hidden after leading whitespace or control characters.
    """
    if isinstance(value, str):
        formula = value.lstrip(" \t\r\n")
        if formula.startswith(("=", "+", "-", "@")):
            return f"'{value}"
    return value


def csv_row(fieldnames: tuple[str, ...], values: list[Any]) -> dict[str, Any]:
    safe_values = (sanitize_csv_string(value) for value in values)
    return dict(zip(fieldnames, safe_values, strict=True))


class AttendanceEventAdminForm(forms.ModelForm):
    """The meeting form, with the two rules an editor would otherwise only find in the guide.

    Both are on the form rather than in the model: help text on a model field is a
    schema change and a migration, and neither of these describes the column.
    """

    class Meta:
        model = AttendanceEvent
        fields = (
            "title",
            "description",
            "start_datetime",
            "end_datetime",
            "allow_non_members",
            "slug",
            "code_secret",
            "code_validity_time",
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # A reader with only the view permission gets a read-only form, and Django
        # leaves its editable fields out of `self.fields` entirely.
        if "slug" in self.fields:
            self.fields["slug"].help_text = _(
                "Mötets del av webbadressen, till exempel hostmote för /attendance/hostmote/. "
                "Bara a-z, 0-9, bindestreck och understreck."
            )
        if "end_datetime" in self.fields:
            self.fields["end_datetime"].help_text = _(
                "Lämna tomt om sluttiden inte är känd. Mötet lämnar då den publika listan 24 timmar efter "
                "starttiden, och rapporten räknar närvaron vid den sista registrerade ändringen. Måste vara "
                "senare än starttiden."
            )


class AttendanceEventAdmin(FlatpickrDateTimeAdminMixin, ModelAdmin):
    # The two times are one field each with the calendar picker the events, news and
    # polls forms use, rather than Django's split date and hour boxes: a board member
    # filling this in should not meet a widget that looks unfinished in dark mode.
    flatpickr_datetime_fields = ("start_datetime", "end_datetime")
    # Every other field takes the shared Unfold widget overrides, the way the events,
    # news, polls and static page admins do. Without them a CharField renders as a
    # bare `vTextField` with no border and no padding under Unfold, which on a dark
    # page reads as a grey stripe rather than as something to type in.
    formfield_overrides = {**UNFOLD_FORMFIELD_OVERRIDES}
    form = AttendanceEventAdminForm
    # The workflow is "find the event, open its overview page", so the list carries
    # the status and the times, and the row offers the code and the report. Without
    # this the changelist shows titles only and cannot be searched.
    list_display = (
        "title",
        "status",
        "start_datetime",
        "end_datetime",
        "allow_non_members",
        "code_link",
        "report_link",
    )
    list_filter = ("allow_non_members", "start_datetime")
    search_fields = ("title", "description", "slug")
    date_hierarchy = "start_datetime"
    ordering = ("-start_datetime",)

    # The shared picker's stylesheet and script. Admin Media is not inherited from the
    # mixin, so both admins that use the widget declare it themselves.
    class Media:
        css = {"all": FLATPICKR_ADMIN_CSS + ("attendance/css/admin-colours.css",)}
        js = ("admin/js/jquery.init.js",) + FLATPICKR_ADMIN_JS

    # No inline of the changes: Django does not paginate an inline, so a meeting
    # with a few hundred people draws one editable form per check-in and the page
    # stops loading. The change list is linked from `event_links` instead, filtered
    # to the meeting, and it has the filters and the date drill-down for the rest.

    # The person filling this in is a board member, not a developer setting up a
    # code generator, so the meeting comes first and the two fields that produce
    # the rotating code sit together in a collapsed section of their own. The
    # links stand between them because they are what the meeting is opened
    # through: the check-in page a participant uses and the staff overview that
    # shows the code. Every field stays editable and nothing is hidden.
    fieldsets = (
        (
            _("Mötet"),
            {
                "fields": ("title", "description", "start_datetime", "end_datetime", "allow_non_members", "slug"),
            },
        ),
        (
            None,
            {"fields": ("event_links",)},
        ),
        (
            _("Koden"),
            {
                "fields": ("code_secret", "code_validity_time"),
                "classes": ("collapse",),
                # The board changes the secret when the code has leaked, so the
                # sentence says what that does and what the period below means.
                "description": _(
                    "Koden som visas på översiktsvyn räknas fram ur hemligheten, så en ny hemlighet gör att "
                    "koden som gäller just nu slutar fungera med en gång. Giltighetsperioden är hur många "
                    "sekunder varje kod är giltig."
                ),
            },
        ),
    )
    readonly_fields = ("event_links",)

    def get_list_display(self, request):
        list_display = list(super().get_list_display(request))
        if not hasattr(request, "user"):
            return list_display
        # The report is the same permission the changelist itself asks for, so
        # this only drops the button on a page the reader could not open anyway.
        # It is here because every other admin action link in this project is
        # gated the same way, and a column that is always present but not always
        # usable is the shape the gate exists to prevent.
        if not self.has_view_permission(request):
            list_display.remove("report_link")
        return list_display

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            re_path(
                r"^(?P<event_id>.+)/report/$",
                self.admin_site.admin_view(self.report),
                name="attendance_event_report",
            ),
            re_path(
                r"^(?P<event_id>.+)/report/timeline\.csv$",
                self.admin_site.admin_view(self.report_timeline_csv),
                name="attendance_event_report_timeline_csv",
            ),
            re_path(
                r"^(?P<event_id>.+)/report/polls\.csv$",
                self.admin_site.admin_view(self.report_polls_csv),
                name="attendance_event_report_polls_csv",
            ),
        ]
        return custom_urls + urls

    @admin.display(description=_("Rapport"))
    def report_link(self, obj):
        return format_html(
            '<a class="button admin-inline-action" href="{}">{}</a>',
            reverse("admin:attendance_event_report", args=[obj.pk]),
            _("Rapport"),
        )

    @admin.display(description=_("Status"))
    def status(self, obj):
        """The three states the report names, so the running meeting is findable here too.

        The list is ordered by start time, which puts a meeting scheduled for next
        week above the one happening now; the coloured word is what tells them
        apart without opening a row.
        """
        if obj.has_ended:
            css, label = "ended", _("Avslutat")
        elif obj.has_started:
            css, label = "running", _("Pågår")
        else:
            css, label = "upcoming", _("Inte startat")

        return format_html('<span class="attendance-status--{}">{}</span>', css, label)

    @admin.display(description=_("Kod"))
    def code_link(self, obj):
        """The overview page with the current code, which is what an operator needs mid-meeting."""
        return format_html(
            '<a class="button admin-inline-action" href="{}" target="_blank" rel="noopener noreferrer">{}</a>',
            reverse("attendance-event-overview", args=[obj.slug]),
            _("Visa möteskoden"),
        )

    @admin.display(description=_("Länkar"))
    def event_links(self, obj) -> SafeString:
        """The pages an operator opens from this meeting, without a built URL.

        The add page has no object yet, so there is no slug to point at and
        nothing to link to. It gets an empty element rather than an empty string,
        because Unfold renders its own "-" placeholder for any falsy readonly
        value; this way the add page shows nothing at all under either theme.
        Every link opens in a new tab so a half-filled form is not left behind,
        and the changes are a filtered change list rather than an inline, because
        an inline would render one form per change.
        """
        if not obj or not obj.pk:
            return format_html("<span>{}</span>", "")

        return format_html(
            '<a class="button admin-inline-action" href="{}" target="_blank" rel="noopener noreferrer">{}</a>'
            '&nbsp;<a class="button admin-inline-action" href="{}" target="_blank" rel="noopener noreferrer">{}</a>'
            '&nbsp;<a class="button admin-inline-action" href="{}?event__id__exact={}" target="_blank" '
            'rel="noopener noreferrer">{}</a>',
            obj.get_absolute_url(),
            _("Öppna incheckningen"),
            reverse("attendance-event-overview", args=[obj.slug]),
            _("Visa möteskoden"),
            reverse("admin:attendance_attendancechange_changelist"),
            obj.pk,
            _("Visa ändringarna"),
        )

    def _event(self, request: HttpRequest, event_id: str) -> AttendanceEvent:
        """The event named by the URL, or a 404, after re-checking the permission.

        ``admin_view`` only proves the reader is staff. An unknown id is a 404
        rather than a 403, so the page does not confirm which ids exist.
        """
        if not self.has_view_permission(request):
            raise PermissionDenied

        return get_object_or_404(self.get_queryset(request), pk=event_id)

    def _changes(self, event: AttendanceEvent) -> list[AttendanceChange]:
        """The whole timeline in chronological order, in one query.

        ``select_related`` so the names cost one query rather than one per row,
        and the explicit ``order_by`` because the model orders newest first and
        both the page and the CSV are read oldest first.
        """
        return list(event.attendance_changes.select_related("user", "non_member").order_by("timestamp", "pk"))

    def _polls(self, event: AttendanceEvent, headcount: int) -> list[dict[str, Any]]:
        """One entry per poll attached to the meeting, with its choices and numbers.

        The choices are ordered explicitly: ``Choice`` has no ``Meta.ordering``,
        so without this the database decides the row order.
        """
        from polls.models import ANYONE

        polls = []
        for poll in event.polls.select_related("question").order_by("pk"):
            question = poll.question
            choices = list(question.choice_set.order_by("pk"))
            # The ballot count is the sum of the choices rather than the number of
            # people: a multiple-choice poll lets one voter cast several, and so
            # does a poll open to anyone. Summing the choices already loaded here
            # keeps it to one query per poll, where a percentage that asked the
            # question per choice went back to the database once for every bar.
            ballots = sum(choice.votes for choice in choices)
            polls.append(
                {
                    "question": question,
                    "ended": question.end_vote,
                    "multiple_choice": question.multiple_choice,
                    "anyone": question.voting_options == ANYONE,
                    "choices": [
                        {
                            "choice": choice,
                            "votes": choice.votes,
                            "percentage": int((choice.votes / ballots) * 100) if ballots else 0,
                        }
                        for choice in choices
                    ],
                    "ballots": ballots,
                    "voters": question.voters.count(),
                    "headcount": headcount,
                }
            )

        return polls

    def report(self, request: HttpRequest, event_id: str):
        event = self._event(request, event_id)
        changes = self._changes(event)
        headcount = present_at_end(event)
        # The poll results are behind polls.view_question, and a reader without it
        # is told they are there rather than left to wonder where they went.
        show_polls = request.user.has_perm("polls.view_question")
        context = {
            **self.admin_site.each_context(request),
            # Deliberately no "title": the admin base template renders that as a
            # heading of its own above the content, and the page already has the
            # meeting's title as its one h1. The page's own name lives in the
            # template's `title` block and in the subtitle under the h1.
            "opts": self.model._meta,
            "event": event,
            # The rows the page draws, capped; the numbers above them and the two
            # downloads still read every change.
            "changes": changes[:REPORT_TIMELINE_ROWS],
            "timeline_shown": min(len(changes), REPORT_TIMELINE_ROWS),
            "timeline_total": len(changes),
            "present_at_end": headcount,
            # Which of the two numbers ``present_at_end()`` returned, so the page
            # can label it honestly: a meeting without an end time has no end to
            # be present at.
            "has_end_datetime": event.end_datetime is not None,
            "present_at_end_label": present_at_end_label(event),
            "peak_present": peak_present_count(changes, event.end_datetime),
            "ever_present": ever_present_count(changes),
            "change_count": len(changes),
            "show_polls": show_polls,
            "hidden_polls": not show_polls and event.polls.exists(),
            "polls": self._polls(event, headcount) if show_polls else [],
            "event_change_url": reverse("admin:attendance_attendanceevent_change", args=[event.pk]),
            "changes_url": f"{reverse('admin:attendance_attendancechange_changelist')}?event__id__exact={event.pk}",
            "timeline_csv_url": reverse("admin:attendance_event_report_timeline_csv", args=[event.pk]),
            "polls_csv_url": reverse("admin:attendance_event_report_polls_csv", args=[event.pk]),
        }

        return render(request, "admin/attendance/report.html", context)

    def _csv_response(self, event: AttendanceEvent, prefix: str) -> HttpResponse:
        return HttpResponse(
            content_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="{report_filename(event, prefix)}"'},
        )

    def report_timeline_csv(self, request: HttpRequest, event_id: str) -> HttpResponse:
        """The timeline as one row per change, for the minutes or the archive."""
        event = self._event(request, event_id)
        fieldnames = tuple(str(label) for label in TIMELINE_FIELDNAMES)
        response = self._csv_response(event, "narvaro")
        # The BOM goes in before the writer so it is the first thing in the body.
        response.write(UTF8_BOM)
        writer = csv.DictWriter(response, fieldnames=fieldnames, delimiter=CSV_DELIMITER)
        writer.writeheader()

        for change in self._changes(event):
            writer.writerow(
                csv_row(
                    fieldnames,
                    [
                        local_timestamp(change.timestamp),
                        change.attendee_name,
                        change_action_label(change),
                        attendee_kind_label(change),
                    ],
                )
            )

        return response

    def report_polls_csv(self, request: HttpRequest, event_id: str) -> HttpResponse:
        """One row per poll per choice, carrying the same numbers the page shows.

        The ballot count, the voter count and the headcount belong to the poll
        rather than to the choice, so they repeat on every row of that poll: that
        is what makes a row readable on its own once it has been sorted and
        filtered away from the others.
        """
        # The download carries the same results the page hides behind this
        # permission, so it needs it too, and the check comes first so a reader
        # who can never have the file cannot probe which ids exist either.
        if not request.user.has_perm("polls.view_question"):
            raise PermissionDenied

        event = self._event(request, event_id)
        fieldnames = tuple(str(label) for label in (*POLL_FIELDNAMES, present_at_end_label(event)))
        response = self._csv_response(event, "omrostning")
        response.write(UTF8_BOM)
        writer = csv.DictWriter(response, fieldnames=fieldnames, delimiter=CSV_DELIMITER)
        writer.writeheader()

        for poll in self._polls(event, present_at_end(event)):
            for entry in poll["choices"]:
                writer.writerow(
                    csv_row(
                        fieldnames,
                        [
                            str(poll["question"].question_text),
                            str(entry["choice"].choice_text),
                            entry["votes"],
                            entry["percentage"],
                            poll["ballots"],
                            poll["voters"],
                            poll["headcount"],
                        ],
                    )
                )

        return response


def member_display_name(member: Member) -> str:
    """The name the board knows a member by.

    ``get_full_name()`` is first and last name, and a member may have neither, so
    the username is the fallback rather than the label: a list of "medlem054" is
    what the change list used to show, and nobody reads who that is.
    """
    return (member.get_full_name() or "").strip() or member.username


class AttendanceChangeAdminForm(forms.ModelForm):
    """The correction form, with a member picked by name rather than by username."""

    class Meta:
        model = AttendanceChange
        # The admin supplies the fields it draws; this is the model's own set, listed
        # explicitly because the linter forbids "__all__" and a stray field would
        # otherwise slip into the form unseen.
        fields = ("event", "user", "non_member", "timestamp", "type")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        user_field = self.fields.get("user")
        if isinstance(user_field, forms.ModelChoiceField):
            user_field.label_from_instance = member_display_name


class NonMemberAttendeeAdmin(ModelAdmin):
    """The one place a guest's name is corrected, because one row serves every meeting.

    There is no add: a guest row is created by a check-in, so an editor adding one
    would invent an attendee. There is no delete either, because deleting the row
    takes every change recorded under that name with it, which is the history the
    report reads. A rename that collides with another guest is refused by the
    model's two constraints and shown as a field error.
    """

    list_display = ("name", "changes")
    search_fields = ("name",)
    fields = ("name",)
    ordering = ("name",)

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        return queryset.annotate(change_count=Count("attendancechange"))

    @admin.display(description=_("Ändringar"), ordering="change_count")
    def changes(self, obj):
        return obj.change_count

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class AttendanceChangeAdmin(FlatpickrDateTimeAdminMixin, ModelAdmin):
    # A correction of last resort, so the time is edited with the same picker as the
    # meeting's own times rather than with the split date and hour boxes.
    flatpickr_datetime_fields = ("timestamp",)
    formfield_overrides = {**UNFOLD_FORMFIELD_OVERRIDES}
    form = AttendanceChangeAdminForm

    list_display = ("timestamp", "attendee", "change_direction")
    list_filter = ("type",)
    search_fields = (
        "event__title",
        "user__username",
        "user__first_name",
        "user__last_name",
        "non_member__name",
    )
    date_hierarchy = "timestamp"
    ordering = ("-timestamp",)
    # The attendee column reads both attendee relations per row, and a method in
    # `list_display` no longer gets the automatic select_related a plain field got.
    list_select_related = ("event", "user", "non_member")
    # Unfold's header is a breadcrumb built from the model, not the `title` this
    # view sets, so the meeting is named in this line above the table. The classic
    # admin ignores the attribute and carries the meeting in the page title.
    list_before_template = "admin/attendance/attendancechange/meeting.html"

    def changelist_view(self, request, extra_context=None):
        """The list belongs to one meeting, so it is only shown for one.

        A meeting is the page the board works from, and a meeting's changes are
        read in the context of that meeting: an unfiltered list of every change
        ever recorded is not a page anybody opens on purpose. Without a meeting in
        the query string the operator is sent to the meeting list, which is where
        one is chosen.
        """
        event = self._event_for_request(request)
        if event is None:
            return HttpResponseRedirect(reverse("admin:attendance_attendanceevent_changelist"))

        extra_context = {
            **(extra_context or {}),
            "title": f"{_('Närvaroändringar')}: {event.title}",
            "attendance_event": event,
            "attendance_event_change_url": reverse("admin:attendance_attendanceevent_change", args=[event.pk]),
        }
        return super().changelist_view(request, extra_context=extra_context)

    def _event_by_id(self, event_id):
        """The meeting that id names, or None for an empty or unknown one."""
        if not event_id:
            return None
        try:
            return AttendanceEvent.objects.get(pk=event_id)
        except AttendanceEvent.DoesNotExist, TypeError, ValueError:
            return None

    def _event_for_request(self, request):
        """The meeting the query string names, or None when it names none or an unknown one."""
        return self._event_by_id(request.GET.get("event__id__exact"))

    def get_changeform_initial_data(self, request):
        """A row added from a meeting's list starts in that meeting.

        The add link carries the filtered list in ``_changelist_filters``, which is
        how Django already knows where to return after saving; the meeting is in
        that query string, so the select does not have to be filled in by hand.
        """
        initial = super().get_changeform_initial_data(request)
        event = self._event_for_request(request)
        if event is None:
            filters = QueryDict(request.GET.get("_changelist_filters", ""))
            event = self._event_by_id(filters.get("event__id__exact"))
        if event is not None:
            initial["event"] = event.pk
        return initial

    def has_module_permission(self, request):
        """The list is not a module of its own: it belongs to a meeting.

        Its changelist still answers for a meeting's URL, which is the only one
        there is, but the app index and the classic sidebar do not offer a page
        that would only redirect them to the meeting list.
        """
        return False

    def _event_changelist_redirect(self, event_id, request=None):
        """The meeting's list, with whatever the operator was looking at kept intact."""
        filters = request.GET.get("_changelist_filters") if request is not None else None
        if filters:
            query = QueryDict(filters, mutable=True)
            query["event__id__exact"] = event_id
            return HttpResponseRedirect(
                f"{reverse('admin:attendance_attendancechange_changelist')}?{query.urlencode()}"
            )

        return HttpResponseRedirect(
            f"{reverse('admin:attendance_attendancechange_changelist')}?event__id__exact={event_id}"
        )

    def response_add(self, request, obj, post_url_continue=None):
        response = super().response_add(request, obj, post_url_continue)
        if "_continue" in request.POST or "_addanother" in request.POST:
            return response
        return self._event_changelist_redirect(obj.event_id, request)

    def response_change(self, request, obj):
        response = super().response_change(request, obj)
        if "_continue" in request.POST or "_addanother" in request.POST:
            return response
        return self._event_changelist_redirect(obj.event_id, request)

    def delete_view(self, request, object_id, extra_context=None):
        # The row is gone by the time the redirect is chosen, so the meeting it
        # belonged to is kept on the request here.
        obj = self.get_object(request, object_id)
        if obj is not None:
            request.attendance_event_id = obj.event_id
        return super().delete_view(request, object_id, extra_context)

    def response_delete(self, request, obj_display, obj_id):
        response = super().response_delete(request, obj_display, obj_id)
        event_id = getattr(request, "attendance_event_id", None)
        if event_id is None:
            return response
        return self._event_changelist_redirect(event_id, request)

    @admin.display(description=_("Deltagare"))
    def attendee(self, obj):
        """One column for the person, which is one field of two in the model.

        A member is linked to their own page; a guest has no admin page, so the
        name and the marker are the whole cell. Two side by side columns wasted a
        dash on every row and made the list read unlike the site's own tables.
        """
        if obj.user_id is not None:
            return format_html(
                '<a href="{}">{}</a>',
                reverse("admin:members_member_change", args=[obj.user_id]),
                member_display_name(obj.user),
            )
        if obj.non_member_id is not None:
            return str(obj.non_member)

        return "-"

    @admin.display(description=_("Typ"), ordering="type")
    def change_direction(self, obj):
        """The direction in the event page's own green and amber.

        A meeting of a few hundred leaves a list where the word alone is easy to
        lose, and the board scans it for the departures. The word stays, so the
        colour is a second signal rather than the only one.
        """
        css = "enter" if obj.type == AttendanceChange.Type.ENTER else "leave"
        return format_html('<span class="attendance-change--{}">{}</span>', css, change_action_label(obj))

    def save_model(self, request, obj, form, change):
        # A correction can move a row to another meeting, so the meeting it left
        # needs telling too.
        previous_event_id = None
        if change and obj.pk:
            previous_event_id = AttendanceChange.objects.filter(pk=obj.pk).values_list("event_id", flat=True).first()

        super().save_model(request, obj, form, change)
        # An open overview page was built from the row as it stood, and a
        # correction produces no change the feed can append. Reloading it is the
        # only answer that also repairs the feed.
        websocket.send_attendance_invalidate(obj.event.slug)
        if previous_event_id is not None and previous_event_id != obj.event_id:
            previous = AttendanceEvent.objects.filter(pk=previous_event_id).first()
            if previous is not None:
                websocket.send_attendance_invalidate(previous.slug)

    def delete_model(self, request, obj):
        slug = obj.event.slug
        super().delete_model(request, obj)
        websocket.send_attendance_invalidate(slug)

    def delete_queryset(self, request, queryset):
        slugs = set(queryset.values_list("event__slug", flat=True))
        super().delete_queryset(request, queryset)
        for slug in slugs:
            websocket.send_attendance_invalidate(slug)

    class Media:
        css = {"all": FLATPICKR_ADMIN_CSS + ("attendance/css/admin-colours.css",)}
        js = ("admin/js/jquery.init.js",) + FLATPICKR_ADMIN_JS


admin.site.register(models.AttendanceEvent, AttendanceEventAdmin)
admin.site.register(models.AttendanceChange, AttendanceChangeAdmin)
admin.site.register(models.NonMemberAttendee, NonMemberAttendeeAdmin)
