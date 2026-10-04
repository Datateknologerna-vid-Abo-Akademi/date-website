import csv
from datetime import datetime
from typing import Any

from django.contrib import admin
from django.core.exceptions import PermissionDenied
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, render
from django.urls import re_path, reverse
from django.utils.html import format_html
from django.utils.timezone import localtime
from django.utils.translation import gettext_lazy as _
from django.utils.translation import pgettext_lazy

from . import models
from .models import AttendanceChange, AttendanceEvent

# The report's downloads are read in Excel by a Swedish association admin, where
# the comma is the decimal separator and the list separator is the semicolon.
# Deliberately not the csv module's default, and deliberately not what
# `billing/admin.py` does.
CSV_DELIMITER = ";"
# What makes Excel read the file as UTF-8 rather than as the local codepage,
# which would mangle every "å", "ä" and "ö" in a name.
UTF8_BOM = "\ufeff"

TIMELINE_FIELDNAMES = (_("Tid"), _("Deltagare"), _("Ändring"), _("Typ"))
POLL_FIELDNAMES = (_("Fråga"), _("Val"), _("Röster"), _("Andel (%)"), _("Röstsedlar"), _("Röstande"), _("Närvarande"))


def attendee_identity(change: AttendanceChange) -> tuple[str, int | None]:
    """The key that tells two attendees apart, the same one the overview page uses.

    A member and a guest are different tables, so their primary keys are not
    comparable and the kind has to be part of the identity.
    """
    if change.user_id is not None:
        return ("user", change.user_id)

    return ("non_member", change.non_member_id)


def peak_present_count(changes: list[AttendanceChange]) -> int:
    """The most people in the room at any one moment of the meeting.

    Nothing in the database answers this portably: the peak is not any single
    row, and PostgreSQL's window functions or ``DISTINCT ON`` would not run on
    the SQLite test database either. Replaying the timeline in Python is the one
    answer that is the same on every backend, and the changes are already in
    memory for the page's table.
    """
    present: set[tuple[str, int | None]] = set()
    peak = 0

    for change in changes:
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
    the same every time the report is opened.

    A meeting with no end time is read at its last recorded change rather than
    at the current time: the report is a historical document, and an answer read
    at "now" is whoever is in the room when the page happens to be opened, which
    is a different number after the next check-in. The state after the newest
    ``AttendanceChange`` is fixed with the log, and ``has_end_datetime`` in the
    report's context is what tells the page which of the two the number is.
    With no changes at all the answer is 0.

    ``present_count()`` and not ``present_attendees()``: only the count runs on
    every backend (see the model's NOTE on the distinct query). It is a function
    of its own so that ``PresentAttendeesTests`` can hold this exact number
    against the real ``DISTINCT ON`` query on the one backend that has it.
    """
    if event.end_datetime is not None:
        return event.present_count(event.end_datetime)

    # The newest row, then the count as it stood at that moment: ties in
    # ``timestamp`` are broken by the primary key so the answer cannot depend on
    # the row order the database happens to return.
    latest = event.attendance_changes.order_by("-timestamp", "-pk").first()
    if latest is None:
        return 0

    return event.present_count(latest.timestamp)


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


def csv_row(fieldnames: tuple[str, ...], values: list[Any]) -> dict[str, Any]:
    return dict(zip(fieldnames, values, strict=True))


class AttendanceChangesInline(admin.TabularInline):
    model = models.AttendanceChange
    classes = ["collapse"]


class AttendanceEventAdmin(admin.ModelAdmin):
    # The workflow is "find the event, open its overview page", so the list is
    # ordered newest first and carries the times and the guest switch. Without
    # this the changelist shows titles only and cannot be searched.
    list_display = ("title", "start_datetime", "end_datetime", "allow_non_members", "report_link")
    list_filter = ("allow_non_members", "start_datetime")
    search_fields = ("title", "description", "slug")
    date_hierarchy = "start_datetime"
    ordering = ("-start_datetime",)
    inlines = [AttendanceChangesInline]

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
            # get_total_votes() is the number of ballots, which is the sum of the
            # choices rather than the number of people: a multiple-choice poll
            # lets one voter cast several, and so does a poll open to anyone.
            ballots = question.get_total_votes()
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
                            # get_vote_percentage() divides by the total and
                            # raises ZeroDivisionError when there are no votes.
                            "percentage": choice.get_vote_percentage() if ballots else 0,
                        }
                        for choice in question.choice_set.order_by("pk")
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
            "changes": changes,
            "present_at_end": headcount,
            # Which of the two numbers ``present_at_end()`` returned, so the page
            # can label it honestly: a meeting without an end time has no end to
            # be present at.
            "has_end_datetime": event.end_datetime is not None,
            "peak_present": peak_present_count(changes),
            "ever_present": ever_present_count(changes),
            "change_count": len(changes),
            "show_polls": show_polls,
            "hidden_polls": not show_polls and event.polls.exists(),
            "polls": self._polls(event, headcount) if show_polls else [],
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
        fieldnames = tuple(str(label) for label in POLL_FIELDNAMES)
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


class AttendanceChangeAdmin(admin.ModelAdmin):
    list_display = ("timestamp", "event", "user", "non_member", "type")
    list_filter = ("type", "event")
    search_fields = (
        "event__title",
        "user__username",
        "user__first_name",
        "user__last_name",
        "non_member__name",
    )
    date_hierarchy = "timestamp"
    ordering = ("-timestamp",)


admin.site.register(models.AttendanceEvent, AttendanceEventAdmin)
admin.site.register(models.AttendanceChange, AttendanceChangeAdmin)
