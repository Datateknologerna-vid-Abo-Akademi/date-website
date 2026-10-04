"""Tests for the attendance app.

An ``AttendanceEvent`` hands out a rotating TOTP code that staff read from the
overview page and that members (and, where the event allows it, guests) type in
on the detail page. Every check-in and check-out becomes an ``AttendanceChange``
row, and the change is broadcast over the event's websocket group.

Two pieces of production code cannot run as written on the SQLite test database,
so the suite works around them instead of dropping the behaviour:

* ``AttendanceEvent.present_attendees()`` uses ``distinct("user", "non_member")``,
  which only PostgreSQL supports (the model carries a ``NOTE`` saying so). The
  detail view calls it on every render, so the view tests patch it out, and the
  class that exercises it is skipped unless the connection is PostgreSQL. The
  presence transitions it computes are covered portably through
  ``is_attendee_present()`` and ``was_attendee_present()``.
* ``django_otp`` reads the clock through the ``time`` name in ``django_otp.oath``,
  so the code tests patch that name. Patching ``time.time`` would not be seen.

``AttendanceChange.timestamp`` defaults to the ``now()`` object the field captured
at import time, so row timestamps are passed in explicitly and cannot be patched.
The patchable ``attendance.models.now`` seam (a module global looked up on each
call) is used for ``has_ended``, which reads it at call time.
"""

import asyncio
import unittest
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from channels.routing import URLRouter
from channels.testing import WebsocketCommunicator
from django.conf import settings
from django.contrib import admin
from django.contrib.auth.models import AnonymousUser, Group
from django.core.exceptions import ValidationError
from django.db import IntegrityError, connection, transaction
from django.test import RequestFactory, TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone, translation
from django.utils.timezone import now
from django_otp.oath import TOTP

if "attendance" not in settings.INSTALLED_APPS:
    raise unittest.SkipTest("attendance app is not installed in this settings module")

from attendance import forms, limits, websocket  # noqa: E402
from attendance.models import AttendanceChange, AttendanceEvent, NonMemberAttendee  # noqa: E402
from attendance.routing import websocket_urlpatterns  # noqa: E402
from members.models import Member  # noqa: E402

# RFC 6238 test key. At second OATH_TIME the current token is PINNED_CODE, and one
# step later it is PINNED_NEXT_CODE, which is what makes the rotation testable.
TOTP_KEY = "12345678901234567890"
OATH_TIME = 59.0
PINNED_CODE = 287082
PINNED_NEXT_CODE = 359152

# The first configured staff group: membership is what makes a member staff.
STAFF_GROUP = settings.STAFF_GROUPS[0]

ENTER = AttendanceChange.Type.ENTER
LEAVE = AttendanceChange.Type.LEAVE

REFERENCE_NOW = datetime(2024, 5, 1, 12, 0, tzinfo=UTC)


def make_member(username, **kwargs):
    """A login-capable member, with any extra profile fields the test needs."""
    return Member.objects.create_user(username=username, password="pwd", **kwargs)


def make_event(slug="mote", title="Möte", start_datetime=None, **kwargs):
    """An attendance event that is open right now and uses the pinned code key."""
    kwargs.setdefault("code_secret", TOTP_KEY)
    return AttendanceEvent.objects.create(
        title=title,
        slug=slug,
        start_datetime=start_datetime or timezone.now(),
        **kwargs,
    )


def record_change(event, change_type, *, user=None, non_member=None, timestamp=None):
    """Write one attendance change. The timestamp is explicit so the order is fixed."""
    return AttendanceChange.objects.create(
        event=event,
        user=user,
        non_member=non_member,
        type=change_type,
        **({"timestamp": timestamp} if timestamp is not None else {}),
    )


def connect_as(user, slug):
    """A websocket communicator for ``ws/attendance/<slug>`` that sees *user*.

    The communicator runs inside a single event loop (see the tests), and the real
    routing is used so the URL pattern and the consumer under it are both covered.
    """
    communicator = WebsocketCommunicator(URLRouter(websocket_urlpatterns), f"/ws/attendance/{slug}")
    communicator.scope["user"] = user
    return communicator


async def receive_message(channel_layer, channel, timeout=1):
    """Receive one channel message, failing after a timeout instead of blocking forever."""
    return await asyncio.wait_for(channel_layer.receive(channel), timeout)


class AttendanceEventModelTests(TestCase):
    """Naming, ending, slug uniqueness and validity-period validation on AttendanceEvent."""

    def test_str_is_the_title(self):
        self.assertEqual(str(make_event(title="Årsmöte")), "Årsmöte")

    @patch("attendance.models.now", return_value=REFERENCE_NOW)
    def test_has_ended_is_false_without_an_end(self, _now):
        self.assertFalse(make_event().has_ended)

    @patch("attendance.models.now", return_value=REFERENCE_NOW)
    def test_has_ended_is_true_after_the_end(self, _now):
        event = make_event(end_datetime=REFERENCE_NOW - timedelta(minutes=1))
        self.assertTrue(event.has_ended)

    @patch("attendance.models.now", return_value=REFERENCE_NOW)
    def test_has_ended_is_false_before_the_end(self, _now):
        event = make_event(end_datetime=REFERENCE_NOW + timedelta(minutes=1))
        self.assertFalse(event.has_ended)

    def test_slug_is_unique(self):
        make_event(slug="arsmote")
        with self.assertRaises(IntegrityError), transaction.atomic():
            make_event(slug="arsmote")

    def test_code_validity_time_of_zero_is_rejected(self):
        event = make_event(code_validity_time=0)

        with self.assertRaises(ValidationError) as raised:
            event.full_clean()

        self.assertIn("code_validity_time", raised.exception.message_dict)

    def test_negative_code_validity_time_is_rejected(self):
        event = make_event(code_validity_time=-30)

        with self.assertRaises(ValidationError) as raised:
            event.full_clean()

        self.assertIn("code_validity_time", raised.exception.message_dict)

    def test_code_validity_time_of_one_second_is_accepted(self):
        event = make_event(code_validity_time=1)

        event.full_clean()  # No ValidationError: one second is the smallest allowed period.

    def test_admin_form_rejects_a_zero_period(self):
        request = RequestFactory().get("/admin/attendance/attendanceevent/")
        request.user = make_member("admin", is_superuser=True)
        form_class = admin.site._registry[AttendanceEvent].get_form(request)
        event = make_event(slug="admin", code_validity_time=0)

        form = form_class(
            data={
                "title": event.title,
                "description": "",
                "start_datetime": event.start_datetime,
                "end_datetime": "",
                "allow_non_members": "on",
                "code_secret": event.code_secret,
                "code_validity_time": "0",
                "slug": event.slug,
            },
            instance=event,
        )

        self.assertFalse(form.is_valid())
        self.assertIn("code_validity_time", form.errors)


class AttendanceCodeTests(TestCase):
    """The rotating code: generation, validity window and time to the next step."""

    @patch("django_otp.oath.time", return_value=OATH_TIME)
    def test_get_current_code_returns_the_current_token(self, _time):
        self.assertEqual(make_event().get_current_code(), PINNED_CODE)

    @patch("django_otp.oath.time", return_value=OATH_TIME)
    def test_is_code_valid_accepts_the_current_token(self, _time):
        self.assertTrue(make_event().is_code_valid(PINNED_CODE))

    @patch("django_otp.oath.time", return_value=OATH_TIME)
    def test_is_code_valid_rejects_a_wrong_code(self, _time):
        self.assertFalse(make_event().is_code_valid(PINNED_CODE + 1))

    @patch("django_otp.oath.time", return_value=OATH_TIME + 30)
    def test_is_code_valid_accepts_the_previous_step_as_grace(self, _time):
        event = make_event()
        # A step later the event hands out a different code ...
        self.assertEqual(event.get_current_code(), PINNED_NEXT_CODE)
        # ... and the code from the step before still verifies, so somebody who
        # started typing just before the rotation is not told they are wrong.
        self.assertTrue(event.is_code_valid(PINNED_CODE))

    @patch("django_otp.oath.time", return_value=OATH_TIME + 60)
    def test_is_code_valid_rejects_a_code_two_steps_old(self, _time):
        event = make_event()

        # The grace is one step wide, not an open window.
        self.assertFalse(event.is_code_valid(PINNED_CODE))

    @patch("django_otp.oath.time", return_value=OATH_TIME)
    def test_time_until_next_code_is_within_the_validity_time(self, _time):
        event = make_event()
        remaining = event.time_until_next_code()
        self.assertGreater(remaining, 0)
        self.assertLessEqual(remaining, event.code_validity_time)

    @patch("django_otp.oath.time", return_value=OATH_TIME + 60)
    def test_code_uses_the_secret_and_period_stored_on_the_event(self, _time):
        secret = "abcdefghijklmnopqrst"
        # Both periods are past their first step at this clock. A 60-second period
        # pinned at OATH_TIME sits at counter 0, and the one-step grace would look
        # at counter -1, which the TOTP arithmetic cannot express.
        minute_period = make_event(code_secret=secret, code_validity_time=60)
        half_minute_period = make_event(slug="trettio", code_secret=secret, code_validity_time=30)

        expected = TOTP(minute_period.code_secret.encode(), step=60).token()

        self.assertEqual(minute_period.get_current_code(), expected)
        self.assertTrue(minute_period.is_code_valid(expected))

        # The same secret on the default 30-second period is a different token, and
        # the 60-second event does not accept it.
        thirty_second_code = half_minute_period.get_current_code()
        self.assertEqual(thirty_second_code, TOTP(secret.encode(), step=30).token())
        self.assertFalse(minute_period.is_code_valid(thirty_second_code))


class AttendeePresenceTests(TestCase):
    """Presence as the views read it: is_attendee_present() and was_attendee_present()."""

    def setUp(self):
        self.event = make_event()
        self.member = make_member("medlem", first_name="Maja", last_name="Andersson")
        self.other_member = make_member("annan", first_name="Nils", last_name="Nordin")
        self.non_member = NonMemberAttendee.objects.create(name="Gäst")
        self.at = now()

    def test_no_changes_means_not_present(self):
        self.assertFalse(self.event.is_attendee_present(self.member))
        self.assertFalse(self.event.was_attendee_present(self.member))

    def test_enter_marks_present(self):
        record_change(self.event, ENTER, user=self.member, timestamp=self.at - timedelta(minutes=2))

        self.assertTrue(self.event.is_attendee_present(self.member))
        self.assertTrue(self.event.was_attendee_present(self.member))

    def test_leave_after_enter_marks_absent(self):
        record_change(self.event, ENTER, user=self.member, timestamp=self.at - timedelta(minutes=2))
        record_change(self.event, LEAVE, user=self.member, timestamp=self.at - timedelta(minutes=1))

        self.assertFalse(self.event.is_attendee_present(self.member))

    def test_enter_after_leave_marks_present_again(self):
        record_change(self.event, ENTER, user=self.member, timestamp=self.at - timedelta(minutes=3))
        record_change(self.event, LEAVE, user=self.member, timestamp=self.at - timedelta(minutes=2))
        record_change(self.event, ENTER, user=self.member, timestamp=self.at - timedelta(minutes=1))

        self.assertTrue(self.event.is_attendee_present(self.member))
        self.assertTrue(self.event.was_attendee_present(self.member))

    def test_former_attendee_was_present_even_after_leaving(self):
        record_change(self.event, ENTER, user=self.member, timestamp=self.at - timedelta(minutes=2))
        record_change(self.event, LEAVE, user=self.member, timestamp=self.at - timedelta(minutes=1))

        self.assertTrue(self.event.was_attendee_present(self.member))
        self.assertFalse(self.event.was_attendee_present(self.other_member))

    def test_leave_without_enter_is_not_a_former_attendee(self):
        record_change(self.event, LEAVE, user=self.member, timestamp=self.at - timedelta(minutes=1))

        self.assertFalse(self.event.was_attendee_present(self.member))

    def test_after_timestamp_limits_the_considered_changes(self):
        entered_at = self.at - timedelta(hours=2)
        record_change(self.event, ENTER, user=self.member, timestamp=entered_at)

        self.assertTrue(self.event.is_attendee_present(self.member))
        # Changes at exactly the timestamp count, later ones alone do not.
        self.assertTrue(self.event.is_attendee_present(self.member, after_timestamp=entered_at))
        self.assertFalse(self.event.is_attendee_present(self.member, after_timestamp=entered_at + timedelta(seconds=1)))

    def test_member_and_non_member_are_tracked_independently(self):
        record_change(self.event, ENTER, user=self.member, timestamp=self.at - timedelta(minutes=3))
        record_change(self.event, ENTER, non_member=self.non_member, timestamp=self.at - timedelta(minutes=2))
        record_change(self.event, LEAVE, non_member=self.non_member, timestamp=self.at - timedelta(minutes=1))

        self.assertTrue(self.event.is_attendee_present(self.member))
        self.assertFalse(self.event.is_attendee_present(self.non_member))
        self.assertTrue(self.event.was_attendee_present(self.non_member))
        self.assertFalse(self.event.was_attendee_present(self.other_member))


@unittest.skipUnless(
    connection.vendor == "postgresql",
    "present_attendees uses DISTINCT ON, which SQLite does not support",
)
class PresentAttendeesTests(TestCase):
    """present_attendees() itself, which only PostgreSQL can run (see the module docstring)."""

    def setUp(self):
        self.event = make_event()
        self.member = make_member("narvarande", first_name="Maja", last_name="Andersson")
        self.gone_member = make_member("lamnat", first_name="Nils", last_name="Nordin")
        self.guest = NonMemberAttendee.objects.create(name="Gäst")
        self.at = now()

    def test_latest_change_per_attendee_decides(self):
        record_change(self.event, ENTER, user=self.member, timestamp=self.at - timedelta(minutes=30))
        record_change(self.event, ENTER, user=self.gone_member, timestamp=self.at - timedelta(minutes=20))
        record_change(self.event, LEAVE, user=self.gone_member, timestamp=self.at - timedelta(minutes=10))
        record_change(self.event, ENTER, non_member=self.guest, timestamp=self.at - timedelta(minutes=5))

        self.assertCountEqual(self.event.present_attendees(self.at), [self.member, self.guest])

    def test_changes_after_the_timestamp_are_ignored(self):
        record_change(self.event, ENTER, user=self.member, timestamp=self.at - timedelta(minutes=10))
        record_change(self.event, LEAVE, user=self.member, timestamp=self.at + timedelta(minutes=10))

        self.assertEqual(self.event.present_attendees(self.at), [self.member])

    def test_the_names_come_from_the_same_query_as_the_rows(self):
        """Two attendees cost one query, not three.

        Without ``select_related`` every name is fetched on its own, which is what
        the query count here pins.
        """
        record_change(self.event, ENTER, user=self.member, timestamp=self.at - timedelta(minutes=10))
        record_change(self.event, ENTER, non_member=self.guest, timestamp=self.at - timedelta(minutes=5))

        with self.assertNumQueries(1):
            labels = [attendee.get_full_name() for attendee in self.event.present_attendees(self.at)]

        self.assertEqual(len(labels), 2)


class NonMemberAttendeeModelTests(TestCase):
    """Guest identity: a unique name that stands in for a Member's full name."""

    def test_name_is_unique(self):
        NonMemberAttendee.objects.create(name="Gäst")
        with self.assertRaises(IntegrityError), transaction.atomic():
            NonMemberAttendee.objects.create(name="Gäst")

    def test_get_full_name_matches_the_member_interface(self):
        attendee = NonMemberAttendee.objects.create(name="Gäst")

        self.assertEqual(attendee.get_full_name(), str(attendee))
        self.assertIn("Gäst", attendee.get_full_name())


class AttendanceChangeModelTests(TestCase):
    """Who a change belongs to, how it renders, and the order the log is read in."""

    def setUp(self):
        self.event = make_event(title="Årsmöte")
        self.member = make_member("medlem", first_name="Maja", last_name="Andersson")
        self.non_member = NonMemberAttendee.objects.create(name="Gäst")
        self.at = now()

    def test_attendee_and_attendee_name_for_a_member(self):
        change = AttendanceChange(event=self.event, user=self.member, type=ENTER, timestamp=self.at)

        self.assertEqual(change.attendee, self.member)
        self.assertEqual(change.attendee_name, "Maja Andersson")

    def test_attendee_and_attendee_name_for_a_non_member(self):
        change = AttendanceChange(event=self.event, non_member=self.non_member, type=ENTER, timestamp=self.at)

        self.assertEqual(change.attendee, self.non_member)
        # The bare name: the socket payload is built in the participant's request
        # language while the staff page renders in the staff member's, so the
        # translated marker cannot be part of a label that has to match across it.
        self.assertEqual(change.attendee_name, "Gäst")

    def test_str_names_the_attendee_and_the_event(self):
        change = record_change(self.event, ENTER, user=self.member, timestamp=self.at)

        self.assertIn("Maja Andersson", str(change))
        self.assertIn("Årsmöte", str(change))

    def test_str_is_invalid_for_an_unsaved_row_without_an_attendee(self):
        change = AttendanceChange(event=self.event, type=ENTER, timestamp=self.at)

        self.assertIn("<ogiltig>", str(change))

    def test_str_is_invalid_for_an_unsaved_row_with_two_attendees(self):
        change = AttendanceChange(
            event=self.event, user=self.member, non_member=self.non_member, type=ENTER, timestamp=self.at
        )

        self.assertIn("<ogiltig>", str(change))

    def test_default_queryset_is_newest_first(self):
        # The newest change is inserted first, so insertion order and timestamp
        # order disagree: a queryset that followed insertion order (or id) would
        # read all three the wrong way round.
        newest = record_change(self.event, ENTER, user=self.member, timestamp=self.at)
        middle = record_change(self.event, ENTER, user=self.member, timestamp=self.at - timedelta(minutes=1))
        oldest = record_change(self.event, ENTER, user=self.member, timestamp=self.at - timedelta(minutes=2))
        self.assertLess(newest.pk, oldest.pk)

        newest_first = [newest, middle, oldest]
        self.assertEqual(list(AttendanceChange.objects.all()), newest_first)
        self.assertEqual(list(self.event.attendance_changes.all()), newest_first)
        self.assertEqual(AttendanceChange.objects.first(), newest)
        self.assertEqual(AttendanceChange.objects.latest(), newest)


class AttendanceChangeConstraintTests(TestCase):
    """The database refuses a change that points at no attendee, or at both kinds."""

    def setUp(self):
        self.event = make_event()
        self.member = make_member("medlem")
        self.non_member = NonMemberAttendee.objects.create(name="Gäst")

    def test_row_with_one_attendee_saves(self):
        change = record_change(self.event, ENTER, user=self.member)

        self.assertIsNotNone(change.pk)

    def test_row_without_an_attendee_is_rejected(self):
        with self.assertRaises(IntegrityError) as raised, transaction.atomic():
            record_change(self.event, ENTER)

        self.assertIn("foreign_keys_ok", str(raised.exception))

    def test_row_with_two_attendees_is_rejected(self):
        with self.assertRaises(IntegrityError) as raised, transaction.atomic():
            record_change(self.event, ENTER, user=self.member, non_member=self.non_member)

        self.assertIn("foreign_keys_ok", str(raised.exception))


class AttendanceChangeFormTests(TestCase):
    """The form checks shapes only: code correctness and conflicts belong to the view."""

    def test_enter_submission_is_valid(self):
        form = forms.AttendanceChangeForm({"non_member_name": "", "type": "0", "code": "123456"})

        self.assertTrue(form.is_valid())
        self.assertIs(form.cleaned_data["type"], ENTER)
        self.assertEqual(form.cleaned_data["code"], 123456)

    def test_leave_submission_is_valid(self):
        form = forms.AttendanceChangeForm({"non_member_name": "Gäst", "type": "1", "code": "123456"})

        self.assertTrue(form.is_valid())
        self.assertIs(form.cleaned_data["type"], LEAVE)

    def test_non_numeric_type_is_a_validation_error(self):
        form = forms.AttendanceChangeForm({"type": "abc", "code": "123456"})

        self.assertFalse(form.is_valid())
        self.assertIn("type", form.errors)

    def test_unknown_type_is_a_validation_error(self):
        form = forms.AttendanceChangeForm({"type": "2", "code": "123456"})

        self.assertFalse(form.is_valid())
        self.assertIn("type", form.errors)

    def test_non_numeric_code_is_a_validation_error(self):
        form = forms.AttendanceChangeForm({"type": "0", "code": "abc"})

        self.assertFalse(form.is_valid())
        self.assertIn("code", form.errors)

    def test_empty_code_is_left_for_the_view_to_reject(self):
        form = forms.AttendanceChangeForm({"type": "0", "code": ""})

        self.assertTrue(form.is_valid())
        self.assertIsNone(form.cleaned_data["code"])

    def test_non_member_name_is_optional(self):
        form = forms.AttendanceChangeForm({"type": "0", "code": "1"})

        self.assertTrue(form.is_valid())
        self.assertEqual(form.cleaned_data["non_member_name"], "")


class AttendanceViewTestCase(TestCase):
    """Shared fixtures for the attendance views.

    ``present_attendees()`` cannot run on SQLite (see the module docstring) and
    the detail view calls it on every render, so every view test patches it out.
    """

    def setUp(self):
        patcher = patch.object(AttendanceEvent, "present_attendees", return_value=[])
        patcher.start()
        self.addCleanup(patcher.stop)

        self.event = make_event()
        self.member = make_member("medlem", first_name="Maja", last_name="Andersson")
        self.staff = make_member("funktionar", first_name="Stina", last_name="Styrelse")
        self.staff.groups.add(Group.objects.create(name=STAFF_GROUP))
        self.detail_url = reverse("attendance-event-view", args=[self.event.slug])
        self.overview_url = reverse("attendance-event-overview", args=[self.event.slug])


class AttendanceIndexViewTests(TestCase):
    """The index lists the events that have not ended yet."""

    def setUp(self):
        self.ended = make_event(slug="avslutat", title="Avslutat", end_datetime=now() - timedelta(hours=1))
        self.ongoing = make_event(slug="pagande", title="Pågående", end_datetime=now() + timedelta(hours=1))
        self.open_ended = make_event(slug="oppet", title="Öppet")
        self.url = reverse("attendance-index")

    def test_index_lists_events_that_have_not_ended(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertCountEqual(response.context["object_list"], [self.ongoing, self.open_ended])
        self.assertContains(response, "Pågående")
        self.assertContains(response, "Öppet")
        self.assertNotContains(response, "Avslutat")

    def test_index_lists_the_soonest_event_first(self):
        make_event(slug="senare", title="Senare", start_datetime=now() + timedelta(days=2))
        make_event(slug="tidigare", title="Tidigare", start_datetime=now() + timedelta(hours=2))

        response = self.client.get(self.url)

        titles = [event.title for event in response.context["object_list"]]
        self.assertLess(titles.index("Tidigare"), titles.index("Senare"))

    def test_index_rejects_post(self):
        self.assertEqual(self.client.post(self.url).status_code, 405)


class AttendanceDetailViewGetTests(AttendanceViewTestCase):
    """Reading the detail page: 404s, guest access and the member's own state."""

    def test_unknown_slug_is_not_found(self):
        response = self.client.get(reverse("attendance-event-view", args=["finns-inte"]))

        self.assertEqual(response.status_code, 404)

    def test_anonymous_guest_sees_the_page_when_non_members_are_allowed(self):
        response = self.client.get(self.detail_url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["object"], self.event)

    def test_anonymous_guest_is_redirected_to_login_when_non_members_are_not_allowed(self):
        self.event.allow_non_members = False
        self.event.save()

        response = self.client.get(self.detail_url)

        self.assertEqual(response.status_code, 302)
        self.assertTrue(response["Location"].startswith(reverse("members:login")))

    def test_member_sees_the_page_when_non_members_are_not_allowed(self):
        self.event.allow_non_members = False
        self.event.save()
        self.client.force_login(self.member)

        response = self.client.get(self.detail_url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["object"], self.event)

    def test_member_sees_their_own_presence_state(self):
        self.client.force_login(self.member)

        response = self.client.get(self.detail_url)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context["is_present"])

        record_change(self.event, ENTER, user=self.member)

        response = self.client.get(self.detail_url)
        self.assertTrue(response.context["is_present"])

    def test_member_presence_state_is_not_affected_by_other_attendees(self):
        record_change(self.event, ENTER, user=self.staff)
        self.client.force_login(self.member)

        response = self.client.get(self.detail_url)

        self.assertFalse(response.context["is_present"])

    def test_present_attendees_are_listed(self):
        guest = NonMemberAttendee.objects.create(name="Gäst I Närvarolistan")
        with patch.object(AttendanceEvent, "present_attendees", return_value=[self.member, guest]) as present:
            response = self.client.get(self.detail_url)

        self.assertEqual(response.status_code, 200)
        present.assert_called_once_with()
        self.assertContains(response, f"<li>{self.member.get_full_name()}</li>")
        self.assertContains(response, f"<li>{guest.get_full_name()}</li>")

    def test_staff_sees_the_change_log(self):
        at = now()
        newest_guest = NonMemberAttendee.objects.create(name="Gäst Senast")
        oldest_guest = NonMemberAttendee.objects.create(name="Gäst Först")
        # Inserted newest first, and every row renders its own attendee's name, so
        # the rendered line order is the only thing the assertions can come from.
        record_change(self.event, ENTER, non_member=newest_guest, timestamp=at)
        record_change(self.event, ENTER, user=self.member, timestamp=at - timedelta(minutes=1))
        record_change(self.event, ENTER, non_member=oldest_guest, timestamp=at - timedelta(minutes=2))
        self.client.force_login(self.staff)

        response = self.client.get(self.detail_url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Närvaroändringar")
        self.assertContains(response, self.member.full_name)

        content = response.content.decode()
        self.assertLess(content.index(newest_guest.name), content.index(self.member.full_name))
        self.assertLess(content.index(self.member.full_name), content.index(oldest_guest.name))

    def test_plain_member_does_not_see_the_change_log(self):
        record_change(self.event, ENTER, user=self.member)
        self.client.force_login(self.member)

        response = self.client.get(self.detail_url)

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Närvaroändringar")

    def test_the_change_log_costs_the_same_however_many_rows_it_has(self):
        """Five more log rows must not mean five more queries."""
        self.client.force_login(self.staff)
        record_change(self.event, ENTER, user=self.member)

        with CaptureQueriesContext(connection) as small:
            self.client.get(self.detail_url)

        for index in range(5):
            guest = NonMemberAttendee.objects.create(name=f"Gäst {index}")
            record_change(self.event, ENTER, non_member=guest)

        with CaptureQueriesContext(connection) as grown:
            self.client.get(self.detail_url)

        self.assertEqual(len(small.captured_queries), len(grown.captured_queries))

    def test_code_from_the_query_string_is_prefilled(self):
        response = self.client.get(self.detail_url, {"code": "123456"})

        self.assertEqual(response.context["prefilled_code"], "123456")
        self.assertContains(response, 'value="123456"')


class AttendanceDetailViewPostTests(AttendanceViewTestCase):
    """Checking in and out: the code, the conflicts and the stored change."""

    def setUp(self):
        super().setUp()
        send_patcher = patch("attendance.views.websocket.send_attendance_change")
        self.send_change = send_patcher.start()
        self.addCleanup(send_patcher.stop)

        time_patcher = patch("django_otp.oath.time", return_value=OATH_TIME)
        time_patcher.start()
        self.addCleanup(time_patcher.stop)

    def post_change(self, change_type, *, code=PINNED_CODE, name=None, login=None, query=""):
        """POST a check-in or check-out, with the code in the body and optionally in the URL."""
        if login is not None:
            self.client.force_login(login)

        data = {"type": str(change_type.value)}
        if code is not None:
            data["code"] = str(code)
        if name is not None:
            data["non_member_name"] = name

        return self.client.post(self.detail_url + query, data)

    def test_wrong_code_is_rejected(self):
        response = self.post_change(ENTER, code=PINNED_CODE + 1, login=self.member)

        self.assertEqual(response.status_code, 403)
        self.assertIn("code_error", response.context)
        self.assertEqual(self.event.attendance_changes.count(), 0)
        self.send_change.assert_not_called()

    def test_missing_code_is_rejected(self):
        response = self.post_change(ENTER, code=None, login=self.member)

        self.assertEqual(response.status_code, 403)
        self.assertEqual(self.event.attendance_changes.count(), 0)
        self.send_change.assert_not_called()

    def test_invalid_change_type_is_rejected(self):
        self.client.force_login(self.member)

        response = self.client.post(self.detail_url, {"type": "9", "code": str(PINNED_CODE)})

        self.assertEqual(response.status_code, 403)
        self.assertIn("type_error", response.context)
        self.assertEqual(self.event.attendance_changes.count(), 0)
        self.assertEqual(NonMemberAttendee.objects.count(), 0)
        self.send_change.assert_not_called()

    def test_enter_creates_the_change_and_redirects_without_the_query(self):
        response = self.post_change(ENTER, login=self.member, query=f"?code={PINNED_CODE}")

        self.assertEqual(response.status_code, 303)
        self.assertEqual(response["Location"], self.detail_url)
        self.assertNotIn("?", response["Location"])

        change = self.event.attendance_changes.get()
        self.assertEqual(change.type, ENTER)
        self.assertEqual(change.user, self.member)
        self.assertIsNone(change.non_member)
        self.send_change.assert_called_once_with(self.event.slug, change)

    def test_member_is_recorded_against_their_own_account(self):
        self.post_change(ENTER, login=self.member)

        change = self.event.attendance_changes.get()
        self.assertEqual(change.user, self.member)
        self.assertEqual(change.attendee, self.member)
        self.assertEqual(change.attendee_name, self.member.full_name)
        self.assertEqual(NonMemberAttendee.objects.count(), 0)

    def test_leave_after_enter_is_recorded(self):
        record_change(self.event, ENTER, user=self.member, timestamp=now() - timedelta(minutes=5))

        response = self.post_change(LEAVE, login=self.member)

        self.assertEqual(response.status_code, 303)
        self.assertEqual(self.event.attendance_changes.count(), 2)
        self.assertEqual(self.event.attendance_changes.first().type, LEAVE)
        self.assertFalse(self.event.is_attendee_present(self.member))

    def test_enter_while_already_present_is_a_conflict(self):
        record_change(self.event, ENTER, user=self.member, timestamp=now() - timedelta(minutes=5))

        response = self.post_change(ENTER, login=self.member)

        self.assertEqual(response.status_code, 409)
        self.assertIn("generic_error", response.context)
        self.assertEqual(self.event.attendance_changes.count(), 1)
        self.send_change.assert_not_called()

    def test_leave_while_not_present_is_a_conflict(self):
        response = self.post_change(LEAVE, login=self.member)

        self.assertEqual(response.status_code, 409)
        self.assertEqual(self.event.attendance_changes.count(), 0)
        self.send_change.assert_not_called()

    def test_anonymous_post_without_a_name_is_rejected(self):
        response = self.post_change(ENTER, name="")

        self.assertEqual(response.status_code, 403)
        self.assertIn("non_member_name_error", response.context)
        self.assertEqual(self.event.attendance_changes.count(), 0)
        self.assertEqual(NonMemberAttendee.objects.count(), 0)

    def test_anonymous_post_with_a_name_creates_and_reuses_the_guest(self):
        response = self.post_change(ENTER, name="Gäst")

        self.assertEqual(response.status_code, 303)
        guest = NonMemberAttendee.objects.get()
        self.assertEqual(guest.name, "Gäst")
        self.assertEqual(self.event.attendance_changes.get().non_member, guest)

        response = self.post_change(LEAVE, name="Gäst")

        self.assertEqual(response.status_code, 303)
        self.assertEqual(NonMemberAttendee.objects.count(), 1)
        self.assertEqual(self.event.attendance_changes.count(), 2)
        self.assertEqual(self.event.attendance_changes.first().non_member, guest)
        self.assertEqual(self.send_change.call_count, 2)

    def test_anonymous_post_with_a_wrong_code_creates_no_guest(self):
        response = self.post_change(ENTER, code=PINNED_CODE + 1, name="Gäst")

        self.assertEqual(response.status_code, 403)
        self.assertEqual(NonMemberAttendee.objects.count(), 0)
        self.assertEqual(self.event.attendance_changes.count(), 0)

    def test_anonymous_post_is_redirected_when_non_members_are_not_allowed(self):
        self.event.allow_non_members = False
        self.event.save()

        response = self.post_change(ENTER, name="Gäst")

        self.assertEqual(response.status_code, 302)
        self.assertTrue(response["Location"].startswith(reverse("members:login")))
        self.assertEqual(self.event.attendance_changes.count(), 0)

    def test_member_enter_is_recorded_when_non_members_are_not_allowed(self):
        self.event.allow_non_members = False
        self.event.save()

        response = self.post_change(ENTER, login=self.member)

        self.assertEqual(response.status_code, 303)
        change = self.event.attendance_changes.get()
        self.assertEqual(change.type, ENTER)
        self.assertEqual(change.user, self.member)
        self.assertIsNone(change.non_member)
        self.send_change.assert_called_once_with(self.event.slug, change)

    def test_a_wrong_code_counts_towards_the_lockout(self):
        response = self.post_change(ENTER, code=PINNED_CODE + 1, login=self.member)

        self.assertEqual(response.status_code, 403)
        self.assertEqual(self.client.session[limits.ATTEMPTS_SESSION_KEY], 1)

    def test_the_lockout_arrives_with_the_last_allowed_wrong_code(self):
        for _ in range(limits.ATTEMPT_LIMIT - 1):
            self.assertEqual(
                self.post_change(ENTER, code=PINNED_CODE + 1, login=self.member).status_code,
                403,
            )

        response = self.post_change(ENTER, code=PINNED_CODE + 1, login=self.member)

        self.assertEqual(response.status_code, 429)
        self.assertIn("lockout_error", response.context)
        self.assertEqual(self.event.attendance_changes.count(), 0)
        self.send_change.assert_not_called()

    def test_a_correct_code_is_refused_while_locked_out(self):
        for _ in range(limits.ATTEMPT_LIMIT):
            self.post_change(ENTER, code=PINNED_CODE + 1, login=self.member)

        response = self.post_change(ENTER, login=self.member)

        self.assertEqual(response.status_code, 429)
        self.assertEqual(self.event.attendance_changes.count(), 0)

    def test_the_lockout_lifts_after_its_window(self):
        start = now()

        with patch("attendance.limits.now", return_value=start) as clock:
            for _ in range(limits.ATTEMPT_LIMIT):
                self.post_change(ENTER, code=PINNED_CODE + 1, login=self.member)

            clock.return_value = start + timedelta(seconds=limits.LOCKOUT_SECONDS + 1)
            response = self.post_change(ENTER, login=self.member)

        self.assertEqual(response.status_code, 303)
        self.assertEqual(self.event.attendance_changes.count(), 1)
        self.assertNotIn(limits.ATTEMPTS_SESSION_KEY, self.client.session)
        self.assertNotIn(limits.LOCKOUT_SESSION_KEY, self.client.session)

    def test_a_correct_code_clears_the_failed_attempts(self):
        for _ in range(2):
            self.post_change(ENTER, code=PINNED_CODE + 1, login=self.member)

        response = self.post_change(ENTER, login=self.member)

        self.assertEqual(response.status_code, 303)
        self.assertNotIn(limits.ATTEMPTS_SESSION_KEY, self.client.session)

    def test_a_malformed_submission_costs_no_attempt(self):
        self.client.force_login(self.member)

        response = self.client.post(self.detail_url, {"type": "9", "code": str(PINNED_CODE)})

        self.assertEqual(response.status_code, 403)
        self.assertNotIn(limits.ATTEMPTS_SESSION_KEY, self.client.session)


class AttendanceOverviewViewTests(AttendanceViewTestCase):
    """The staff-only code view."""

    def setUp(self):
        super().setUp()
        time_patcher = patch("django_otp.oath.time", return_value=OATH_TIME)
        time_patcher.start()
        self.addCleanup(time_patcher.stop)

    def test_anonymous_visitor_is_redirected_to_login(self):
        response = self.client.get(self.overview_url)

        self.assertEqual(response.status_code, 302)
        self.assertTrue(response["Location"].startswith(reverse("members:login")))

    def test_plain_member_is_forbidden(self):
        self.client.force_login(self.member)

        self.assertEqual(self.client.get(self.overview_url).status_code, 403)

    def test_unknown_slug_is_not_found(self):
        self.client.force_login(self.staff)

        response = self.client.get(reverse("attendance-event-overview", args=["finns-inte"]))

        self.assertEqual(response.status_code, 404)

    def test_overview_rejects_post(self):
        self.client.force_login(self.staff)

        self.assertEqual(self.client.post(self.overview_url).status_code, 405)

    def test_staff_group_member_sees_the_current_code(self):
        self.client.force_login(self.staff)

        response = self.client.get(self.overview_url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["code"], PINNED_CODE)
        self.assertContains(response, str(PINNED_CODE))

    def test_superuser_sees_the_current_code(self):
        admin = make_member("admin", is_superuser=True)
        self.client.force_login(admin)

        response = self.client.get(self.overview_url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["code"], PINNED_CODE)

    def test_overview_lists_the_present_attendees(self):
        guest = NonMemberAttendee.objects.create(name="Gäst I Översikten")
        self.client.force_login(self.staff)

        with patch.object(AttendanceEvent, "present_attendees", return_value=[self.member, guest]) as present:
            response = self.client.get(self.overview_url)

        self.assertEqual(response.status_code, 200)
        present.assert_called_once_with()
        member_label = self.member.get_full_name()
        guest_label = guest.name
        self.assertCountEqual(response.context["present_attendees"], [member_label, guest_label])
        self.assertContains(response, "Närvarande")
        # The list updates over the socket, so it has to announce its changes.
        self.assertContains(response, 'aria-live="polite"')
        self.assertContains(response, f'<li data-attendee="{member_label}">{member_label}</li>')
        self.assertContains(response, f'<li data-attendee="{guest_label}">{guest_label}</li>')

    def test_overview_shows_the_empty_state_when_nobody_is_present(self):
        """The empty state is in the page, unhidden, when the event has nobody present."""
        self.client.force_login(self.staff)

        response = self.client.get(self.overview_url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '<ul id="present-attendees"')
        self.assertContains(response, 'id="no-present-attendees"')
        self.assertNotContains(response, 'id="no-present-attendees" hidden')

    def test_websocket_label_matches_the_overview_label_for_a_guest(self):
        """The broadcast carries the label the staff page renders, marker or not.

        ``attendee_name`` is what ``websocket.send_attendance_change`` puts in the
        payload. The list on the page and the payload both come from
        ``attendee_label``, so the script recognises an attendee it has already
        rendered instead of adding a second row for them.
        """
        guest = NonMemberAttendee.objects.create(name="Gäst I Översikten")
        change = record_change(self.event, ENTER, non_member=guest, timestamp=now())
        self.client.force_login(self.staff)

        with patch.object(AttendanceEvent, "present_attendees", return_value=[guest]):
            response = self.client.get(self.overview_url)

        layer = get_channel_layer()
        with patch.object(layer, "group_send", new=AsyncMock()) as group_send:
            websocket.send_attendance_change(self.event.slug, change)

        broadcast_name = group_send.await_args.args[1]["change"]["name"]
        self.assertEqual(broadcast_name, guest.name)
        # The page carries the same label in the same attribute the script reads.
        self.assertContains(response, f'data-attendee="{broadcast_name}"')
        # The translated guest marker belongs to the change log, not to this label.
        self.assertNotContains(response, "icke-medlem")

    def test_the_guest_label_does_not_depend_on_the_language(self):
        """The participant's language and the staff member's may differ.

        The payload is built while the participant checks in and the page is
        rendered in the staff member's language. ``attendee_label`` is therefore
        untranslated, which is why it cannot be the guest's ``get_full_name()``:
        that one appends a translated marker and would not match.
        """
        guest = NonMemberAttendee.objects.create(name="Gäst I Översikten")
        change = record_change(self.event, ENTER, non_member=guest, timestamp=now())

        with translation.override("sv"):
            swedish_label = change.attendee_name
            swedish_log_label = guest.get_full_name()
        with translation.override("en"):
            english_label = change.attendee_name
            english_log_label = guest.get_full_name()

        self.assertEqual(swedish_label, english_label)
        self.assertEqual(swedish_label, guest.name)
        self.assertNotEqual(swedish_log_label, english_log_label)


class AttendanceAdminTests(TestCase):
    """The admin surface an editor works from: find the event, open its overview page."""

    def setUp(self):
        self.admin_user = make_member("admin", is_superuser=True)
        self.changelist_url = reverse("admin:attendance_attendanceevent_changelist")

    def test_event_changelist_lists_the_events(self):
        make_event(slug="hostmote", title="Höstmöte")
        self.client.force_login(self.admin_user)

        response = self.client.get(self.changelist_url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Höstmöte")
        self.assertContains(response, "Starttid")

    def test_event_changelist_can_be_searched(self):
        make_event(slug="hostmote", title="Höstmöte")
        make_event(slug="arsmote", title="Årsmöte")
        self.client.force_login(self.admin_user)

        response = self.client.get(self.changelist_url, {"q": "Höst"})

        self.assertContains(response, "Höstmöte")
        self.assertNotContains(response, "Årsmöte")

    def test_event_changelist_opens_on_the_newest_event(self):
        make_event(slug="aldre", title="Äldre", start_datetime=now() - timedelta(days=7))
        make_event(slug="nyare", title="Nyare", start_datetime=now())
        self.client.force_login(self.admin_user)

        response = self.client.get(self.changelist_url)

        content = response.content.decode()
        self.assertLess(content.index("Nyare"), content.index("Äldre"))


class AttendanceWebsocketTests(TestCase):
    """send_attendance_change() broadcasts one change to the event's group."""

    def setUp(self):
        self.event = make_event(slug="mote")
        self.member = make_member("medlem", first_name="Maja", last_name="Andersson")
        self.channel_layer = get_channel_layer()
        self.group = f"attendance_{self.event.slug}"

    def test_message_targets_the_event_group_with_the_attendee_payload(self):
        change = record_change(self.event, ENTER, user=self.member)

        with patch.object(self.channel_layer, "group_send", new=AsyncMock()) as group_send:
            websocket.send_attendance_change(self.event.slug, change)

        group_send.assert_awaited_once_with(
            "attendance_mote",
            {"type": "attendance.change", "change": {"name": "Maja Andersson", "type": "ENTER"}},
        )

    def test_message_reaches_a_listener_in_the_event_group(self):
        change = record_change(self.event, LEAVE, user=self.member)
        channel = async_to_sync(self.channel_layer.new_channel)()
        async_to_sync(self.channel_layer.group_add)(self.group, channel)
        self.addCleanup(async_to_sync(self.channel_layer.group_discard), self.group, channel)

        websocket.send_attendance_change(self.event.slug, change)

        message = async_to_sync(receive_message)(self.channel_layer, channel)
        self.assertEqual(message["type"], "attendance.change")
        self.assertEqual(message["change"], {"name": "Maja Andersson", "type": "LEAVE"})


class AttendanceConsumerTests(TestCase):
    """The overview websocket: staff get codes, everyone else is rejected.

    Each test runs its whole websocket conversation inside one event loop, because
    the communicator's task lives in the loop that created it.

    Known limitation on PostgreSQL: ``channels``' ``database_sync_to_async`` calls
    ``close_old_connections()`` around the consumer's database access, which closes
    the connection the surrounding ``TestCase`` transaction is using, so on
    PostgreSQL the first test in this class passes and later ones error with
    "connection already closed". ``core.settings.test``, which is what the
    repository runs, uses SQLite, where the in-memory database survives the
    reconnect and all five pass.
    """

    def setUp(self):
        self.event = make_event(slug="motesal")
        self.staff = make_member("funktionar", first_name="Stina", last_name="Styrelse")
        self.staff.groups.add(Group.objects.create(name=STAFF_GROUP))
        self.member = make_member("medlem", first_name="Maja", last_name="Andersson")
        self.channel_layer = get_channel_layer()

    def test_staff_receives_the_current_code(self):
        async def flow():
            communicator = connect_as(self.staff, self.event.slug)
            connected, _ = await communicator.connect(timeout=10)
            self.assertTrue(connected)

            await communicator.send_json_to({"type": "get_code"})
            reply = await communicator.receive_json_from(timeout=10)
            await communicator.disconnect(timeout=10)
            return reply

        with patch("django_otp.oath.time", return_value=OATH_TIME):
            reply = async_to_sync(flow)()

        self.assertEqual(reply["type"], "code")
        self.assertEqual(reply["code"], PINNED_CODE)
        # The patched clock sits at OATH_TIME, one second before the next step.
        self.assertAlmostEqual(reply["until_next"], 1.0)

    def test_non_staff_member_is_rejected(self):
        async def flow():
            communicator = connect_as(self.member, self.event.slug)
            connected, _ = await communicator.connect(timeout=10)
            return connected

        self.assertFalse(async_to_sync(flow)())

    def test_anonymous_visitor_is_rejected(self):
        async def flow():
            communicator = connect_as(AnonymousUser(), self.event.slug)
            connected, _ = await communicator.connect(timeout=10)
            return connected

        self.assertFalse(async_to_sync(flow)())

    def test_unknown_message_type_gets_no_reply(self):
        async def flow():
            communicator = connect_as(self.staff, self.event.slug)
            connected, _ = await communicator.connect(timeout=10)
            self.assertTrue(connected)

            await communicator.send_json_to({"type": "not-a-real-message"})
            # A bounded silence check: the only way to observe that nothing was
            # answered. It returns as soon as anything shows up in the queue.
            silent = await communicator.receive_nothing(timeout=0.1)

            # The connection still answers afterwards, so the unknown type was
            # ignored rather than fatal.
            await communicator.send_json_to({"type": "get_code"})
            reply = await communicator.receive_json_from(timeout=10)
            await communicator.disconnect(timeout=10)
            return silent, reply

        with patch("django_otp.oath.time", return_value=OATH_TIME):
            silent, reply = async_to_sync(flow)()

        self.assertTrue(silent)
        self.assertEqual(reply["type"], "code")
        self.assertEqual(reply["code"], PINNED_CODE)

    def test_attendance_change_from_the_group_is_forwarded(self):
        """The handler reads the name/type payload that websocket.send_attendance_change sends."""

        async def flow():
            communicator = connect_as(self.staff, self.event.slug)
            connected, _ = await communicator.connect(timeout=10)
            self.assertTrue(connected)

            await self.channel_layer.group_send(
                f"attendance_{self.event.slug}",
                {"type": "attendance.change", "change": {"name": "Gäst", "type": "ENTER"}},
            )
            reply = await communicator.receive_json_from(timeout=10)
            await communicator.disconnect(timeout=10)
            return reply

        self.assertEqual(
            async_to_sync(flow)(),
            {"type": "attendance_change", "data": {"name": "Gäst", "type": "ENTER"}},
        )
