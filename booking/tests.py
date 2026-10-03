"""Tests for the booking app.

The public room list and room pages are readable by anyone, but creating a
booking as a visitor without a website account is gated by a code derived from
``SECRET_KEY`` and a generation counter. Nothing about the code is stored: an
unlock is only a per-generation session token, so rotating the code invalidates
existing unlocks by itself and the typed code never reaches the session.
"""

import datetime
import re
import time
import zoneinfo
from types import SimpleNamespace
from unittest.mock import patch

from django.conf import settings
from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.core.exceptions import ValidationError
from django.test import RequestFactory, SimpleTestCase, TestCase
from django.urls import reverse
from django.utils import formats, timezone

from booking import access, emails
from booking.admin import BookingAdmin, BookingInline, BookingOriginFilter, RoomAdmin
from booking.forms import AnonymousBookingForm, BookingForm
from booking.models import BOOKING_PAST_GRACE, Booking, BookingSettings, Closure, Room
from core.admin_ui import get_sidebar_navigation

# Unsaved rooms with an explicit primary key: every code function takes a room,
# so the pure-function tests need no database at all.
FIRST_CODE_ROOM = Room(pk=1, name='Bastun', code_generation=1)
SECOND_GENERATION_ROOM = Room(pk=1, name='Bastun', code_generation=2)
OTHER_ROOM_SAME_GENERATION = Room(pk=2, name='Sauna', code_generation=1)

# core.settings.test pins SECRET_KEY to the literal "SECRET_KEY". These are the
# codes derived from it for room 1's first generations, pinned so a change to the
# derivation (secret, message shape, digest truncation) fails loudly instead of
# silently handing every booker a different code.
PINNED_FIRST_CODE = '212077'
PINNED_SECOND_CODE = '023764'
PINNED_THIRD_CODE = '464066'


def local_input_time(value):
    """Return the value a ``datetime-local`` input submits."""
    return timezone.localtime(value).strftime('%Y-%m-%dT%H:%M')


def make_room(name='Bastun'):
    return Room.objects.create(name=name)


def make_booking(room, start, end, **kwargs):
    return Booking.objects.create(room=room, start=start, end=end, **kwargs)


def make_member(username, **kwargs):
    return get_user_model().objects.create_user(
        username=username,
        password='pwd',
        email=f'{username}@example.com',
        **kwargs,
    )


def make_staff_member(username, group_name, permissions=()):
    """A member in a STAFF_GROUPS group holding the named model permissions."""
    group, _created = Group.objects.get_or_create(name=group_name)
    member = make_member(username)
    member.groups.add(group)
    for app_label, codename in permissions:
        member.user_permissions.add(Permission.objects.get(content_type__app_label=app_label, codename=codename))
    return member


class PinnedNowMixin:
    """Pin ``booking.access.now_at`` to local noon, mid-slot for every period.

    The views take the time from ``access.now_at()``, so patching it there pins
    the whole request path; a test can move ``self.now`` to jump a rotation.
    """

    def setUp(self):
        super().setUp()
        self.now = timezone.localtime(timezone.now()).replace(hour=12, minute=0, second=0, microsecond=0)
        now_patcher = patch('booking.access.now_at', new=lambda: self.now)
        now_patcher.start()
        self.addCleanup(now_patcher.stop)


class BookingCodeDerivationTests(SimpleTestCase):
    """Each room's code is derived from the secret, the room and its generation."""

    def test_code_is_six_digits_and_different_for_each_generation(self):
        codes = [access.code_for_generation(FIRST_CODE_ROOM, generation) for generation in range(1, 6)]

        for code in codes:
            self.assertEqual(len(code), access.BOOKING_CODE_DIGITS)
            self.assertTrue(code.isdigit())
        # A derivation that ignored the generation would hand out one code
        # forever, which is the failure this pins.
        self.assertEqual(len(set(codes)), len(codes))

    def test_two_rooms_on_the_same_generation_get_different_codes(self):
        # The whole point of per-room codes: one room's code says nothing about
        # another's, so a code that leaks for the sauna does not open the office.
        self.assertEqual(FIRST_CODE_ROOM.code_generation, OTHER_ROOM_SAME_GENERATION.code_generation)
        self.assertNotEqual(
            access.code_for_generation(FIRST_CODE_ROOM, 1),
            access.code_for_generation(OTHER_ROOM_SAME_GENERATION, 1),
        )
        self.assertNotEqual(access.current_code(FIRST_CODE_ROOM), access.current_code(OTHER_ROOM_SAME_GENERATION))

    def test_renaming_a_room_keeps_its_code(self):
        # The derivation uses the primary key, not the name, so the board can
        # rename a room without having to tell everybody a new code.
        renamed = Room(pk=1, name='Bastun (renoverad)', code_generation=1)

        self.assertEqual(access.current_code(renamed), PINNED_FIRST_CODE)

    def test_the_known_generations_are_pinned(self):
        self.assertEqual(access.code_for_generation(FIRST_CODE_ROOM, 1), PINNED_FIRST_CODE)
        self.assertEqual(access.code_for_generation(FIRST_CODE_ROOM, 2), PINNED_SECOND_CODE)
        self.assertEqual(access.code_for_generation(FIRST_CODE_ROOM, 3), PINNED_THIRD_CODE)

    def test_the_code_does_not_depend_on_the_clock(self):
        # Nothing about the code moves on its own, so no schedule has to run and
        # a forgotten code stays valid.
        for at in (
            datetime.datetime(2026, 1, 5, 9, 0),
            datetime.datetime(2031, 7, 1, 3, 0),
            datetime.datetime(1999, 12, 31, 23, 59),
        ):
            with self.subTest(at=at), patch('booking.access.now_at', new=lambda at=at: at):
                self.assertEqual(access.current_code(FIRST_CODE_ROOM), PINNED_FIRST_CODE)

    def test_current_code_follows_the_room_generation(self):
        self.assertEqual(access.current_code(FIRST_CODE_ROOM), PINNED_FIRST_CODE)
        self.assertEqual(access.current_code(SECOND_GENERATION_ROOM), PINNED_SECOND_CODE)

    def test_code_is_identical_for_another_association(self):
        # The derivation uses SECRET_KEY, the room and the generation only. Two
        # associations sharing a secret share codes, which is why the docs tell
        # each release to set its own.
        date_code = access.current_code(FIRST_CODE_ROOM)

        with self.settings(PROJECT_NAME='kk'):
            other_code = access.current_code(FIRST_CODE_ROOM)

        self.assertEqual(other_code, date_code)

    def test_a_different_secret_gives_a_different_code(self):
        with self.settings(SECRET_KEY='another-secret'):
            self.assertNotEqual(access.code_for_generation(FIRST_CODE_ROOM, 1), PINNED_FIRST_CODE)


class BookingCodeRotationTests(TestCase):
    """Rotating is the only thing that moves a code, and it is per room."""

    def test_rotating_moves_that_room_to_the_next_generation(self):
        room = make_room(name='Bastun')
        self.assertEqual(room.code_generation, 1)
        self.assertIsNone(room.rotated_at)
        before = access.current_code(room)

        at = timezone.now()
        generation = room.rotate_code(at=at)

        self.assertEqual(generation, 2)
        room.refresh_from_db()
        self.assertEqual(room.code_generation, 2)
        self.assertEqual(room.rotated_at, at)
        self.assertNotEqual(access.current_code(room), before)

    def test_rotating_one_room_leaves_every_other_room_alone(self):
        office = make_room(name='Kansliet')
        sauna = make_room(name='Bastun')
        sauna_code = access.current_code(sauna)
        sauna_state = (sauna.code_generation, sauna.rotated_at)

        office.rotate_code()

        sauna.refresh_from_db()
        self.assertEqual(access.current_code(sauna), sauna_code)
        self.assertEqual((sauna.code_generation, sauna.rotated_at), sauna_state)

    def test_rotating_twice_moves_twice(self):
        room = make_room(name='Bastun')

        room.rotate_code()
        room.rotate_code()

        self.assertEqual(room.code_generation, 3)
        self.assertEqual(access.current_code(room), access.code_for_generation(room, 3))

    def test_rotating_a_room_ends_that_room_s_unlocks_at_once(self):
        # Deliberate asymmetry: the code just handed out keeps working for the
        # grace window, but an unlock granted with the old code does not.
        office = make_room(name='Kansliet')
        sauna = make_room(name='Bastun')
        request = SimpleNamespace(session={})
        access.grant_session(request, office)
        access.grant_session(request, sauna)
        self.assertTrue(access.session_has_access(request, office))
        self.assertTrue(access.session_has_access(request, sauna))

        office.rotate_code()

        self.assertFalse(access.session_has_access(request, office))
        # The other room's unlock is untouched, which is what per-room codes buy.
        self.assertTrue(access.session_has_access(request, sauna))

    def test_the_first_generation_is_the_default(self):
        room = make_room(name='Bastun')

        self.assertEqual(room.code_generation, 1)
        self.assertIsNone(room.rotated_at)


class BookingCodeGraceTests(SimpleTestCase):
    """The previous code keeps working briefly after that room is rotated.

    The window is anchored to the moment of that room's rotation, and a grant
    made during it stores the current generation's token, so an unlock cannot
    outlive the rotation that granted it.
    """

    def setUp(self):
        super().setUp()
        self.rotated_at = datetime.datetime(2026, 1, 5, 9, 0)
        self.after_rotation = Room(
            pk=1,
            name='Bastun',
            code_generation=2,
            rotated_at=timezone.make_aware(self.rotated_at, timezone.get_current_timezone()),
        )
        self.current_code = access.code_for_generation(self.after_rotation, 2)
        self.previous_code = access.code_for_generation(self.after_rotation, 1)

    def test_previous_code_is_accepted_just_after_the_rotation(self):
        at = self.rotated_at + datetime.timedelta(minutes=5)

        self.assertEqual(
            access.accepted_codes(self.after_rotation, at=at),
            (self.current_code, self.previous_code),
        )
        self.assertTrue(access.check_code(self.after_rotation, self.previous_code, at=at))

    def test_previous_code_is_rejected_after_the_grace_window(self):
        at = self.rotated_at + access.BOOKING_CODE_GRACE + datetime.timedelta(minutes=1)

        self.assertEqual(access.accepted_codes(self.after_rotation, at=at), (self.current_code,))
        self.assertFalse(access.check_code(self.after_rotation, self.previous_code, at=at))
        self.assertTrue(access.check_code(self.after_rotation, self.current_code, at=at))

    def test_one_room_s_rotation_does_not_open_another_room_s_window(self):
        # Rotating the office must not make the sauna's old code valid.
        sauna = Room(pk=2, name='Sauna', code_generation=2, rotated_at=None)
        at = self.rotated_at + datetime.timedelta(minutes=5)

        self.assertEqual(
            access.accepted_codes(sauna, at=at),
            (access.code_for_generation(sauna, 2),),
        )
        self.assertFalse(access.check_code(sauna, access.code_for_generation(sauna, 1), at=at))

    def test_there_is_no_grace_before_anything_has_been_rotated(self):
        # The first code has no predecessor to keep alive, and a code that was
        # never handed out must not be accepted.
        fresh = Room(pk=1, name='Bastun', code_generation=1, rotated_at=None)

        self.assertEqual(
            access.accepted_codes(fresh, at=self.rotated_at),
            (access.code_for_generation(fresh, 1),),
        )

    def test_a_rotation_stamped_in_the_future_does_not_open_the_window(self):
        # Clock skew between app servers must not revive the previous code.
        at = self.rotated_at - datetime.timedelta(minutes=1)

        self.assertEqual(access.accepted_codes(self.after_rotation, at=at), (self.current_code,))

    def test_the_window_measures_elapsed_time_across_a_clock_change(self):
        # Helsinki leaves summer time at 04:00 EEST on 2026-10-25, so these two
        # are five minutes apart on the clock and sixty-five in reality. Naive
        # subtraction of two datetimes sharing a tzinfo gets this wrong and
        # keeps a rotated code alive for an extra hour.
        helsinki = zoneinfo.ZoneInfo('Europe/Helsinki')
        rotated_at = datetime.datetime(2026, 10, 25, 3, 55, tzinfo=helsinki)
        at = datetime.datetime(2026, 10, 25, 4, 0, tzinfo=helsinki)
        real_elapsed = at.astimezone(datetime.UTC) - rotated_at.astimezone(datetime.UTC)
        room = Room(pk=1, name='Bastun', code_generation=2, rotated_at=rotated_at)

        with timezone.override('Europe/Helsinki'):
            self.assertGreater(real_elapsed, access.BOOKING_CODE_GRACE)
            self.assertEqual(
                access.accepted_codes(room, at=at),
                (access.code_for_generation(room, 2),),
            )
            self.assertFalse(access.check_code(room, access.code_for_generation(room, 1), at=at))

    def test_the_window_survives_a_clock_change_that_shortens_the_wall_clock(self):
        # The other direction: Helsinki enters summer time at 03:00 EET on
        # 2026-03-29. Ten minutes have passed but the clock says seventy, so
        # naive subtraction would close the window on a booker who was handed
        # the previous code a moment ago.
        helsinki = zoneinfo.ZoneInfo('Europe/Helsinki')
        rotated_at = datetime.datetime(2026, 3, 29, 2, 55, tzinfo=helsinki)
        at = datetime.datetime(2026, 3, 29, 4, 5, tzinfo=helsinki)
        real_elapsed = at.astimezone(datetime.UTC) - rotated_at.astimezone(datetime.UTC)
        room = Room(pk=1, name='Bastun', code_generation=2, rotated_at=rotated_at)

        with timezone.override('Europe/Helsinki'):
            self.assertLess(real_elapsed, access.BOOKING_CODE_GRACE)
            self.assertEqual(
                access.accepted_codes(room, at=at),
                (access.code_for_generation(room, 2), access.code_for_generation(room, 1)),
            )

    def test_grant_during_grace_stores_the_current_generation_token(self):
        request = SimpleNamespace(session={})

        access.grant_session(request, self.after_rotation)

        stored = request.session[access.BOOKING_SESSION_TOKEN_KEY]['1']
        self.assertEqual(stored, access.session_token(self.after_rotation))
        self.assertTrue(access.session_has_access(request, self.after_rotation))
        # The same room one generation earlier is a different unlock, which is
        # how a rotation ends it without storing an expiry.
        previous = Room(pk=1, name='Bastun', code_generation=1)
        self.assertFalse(access.session_has_access(request, previous))


class BookingCodeValidationTests(SimpleTestCase):
    """An empty code is never accepted, so a blank gate cannot unlock."""

    def setUp(self):
        super().setUp()
        self.at = datetime.datetime(2026, 1, 5, 12, 0)

    def test_empty_code_is_never_accepted(self):
        for candidate in ('', None, '   '):
            with self.subTest(candidate=candidate):
                self.assertFalse(access.check_code(FIRST_CODE_ROOM, candidate, at=self.at))

        # Positive control: the loop above must not pass vacuously.
        self.assertTrue(access.check_code(FIRST_CODE_ROOM, access.current_code(FIRST_CODE_ROOM), at=self.at))

    def test_short_or_stretched_codes_are_rejected(self):
        code = access.current_code(FIRST_CODE_ROOM)

        self.assertFalse(access.check_code(FIRST_CODE_ROOM, code[:-1], at=self.at))
        self.assertFalse(access.check_code(FIRST_CODE_ROOM, f'{code}0', at=self.at))

    def test_one_room_s_code_does_not_open_another_room(self):
        # The reason for per-room codes, asserted on the check itself.
        other = OTHER_ROOM_SAME_GENERATION

        self.assertFalse(access.check_code(other, access.current_code(FIRST_CODE_ROOM), at=self.at))
        self.assertTrue(access.check_code(other, access.current_code(other), at=self.at))


class BookingModelTests(TestCase):
    """Overlap, adjacency and ownership rules of the two models."""

    @classmethod
    def setUpTestData(cls):
        cls.room = make_room(name='Bastun')
        cls.other_room = make_room(name='Sauna')
        cls.start = timezone.now() + datetime.timedelta(days=1)
        cls.end = cls.start + datetime.timedelta(hours=1)

    def test_room_str_is_the_name(self):
        self.assertEqual(str(self.room), 'Bastun')

    def test_booking_str_shows_room_and_local_times(self):
        booking = make_booking(self.room, self.start, self.end)

        start = timezone.localtime(self.start).strftime('%Y-%m-%d %H:%M')
        end = timezone.localtime(self.end).strftime('%Y-%m-%d %H:%M')

        self.assertEqual(str(booking), f'Bastun: {start} - {end}')

    def test_end_must_be_after_start(self):
        booking = Booking(room=self.room, start=self.end, end=self.start, booker_name='Någon')

        with self.assertRaises(ValidationError) as raised:
            booking.full_clean()

        self.assertIn('end', raised.exception.message_dict)

    def test_overlapping_booking_in_the_same_room_is_rejected(self):
        make_booking(self.room, self.start, self.end)
        overlapping = Booking(
            room=self.room,
            start=self.start + datetime.timedelta(minutes=15),
            end=self.end + datetime.timedelta(minutes=15),
            booker_name='Någon',
        )

        with self.assertRaises(ValidationError) as raised:
            overlapping.full_clean()

        self.assertIn('start', raised.exception.message_dict)

    def test_adjacent_booking_is_allowed(self):
        make_booking(self.room, self.start, self.end)
        adjacent = Booking(
            room=self.room,
            start=self.end,
            end=self.end + datetime.timedelta(hours=1),
            booker_name='Någon',
        )

        adjacent.full_clean()

    def test_overlapping_booking_in_another_room_is_allowed(self):
        make_booking(self.room, self.start, self.end)
        other = Booking(room=self.other_room, start=self.start, end=self.end, booker_name='Någon')

        other.full_clean()

    def test_editing_a_booking_does_not_clash_with_itself(self):
        booking = make_booking(self.room, self.start, self.end, booker_name='Någon')
        booking.description = 'Uppdaterad beskrivning'

        booking.full_clean()

    def test_external_booking_needs_a_booker_name(self):
        booking = Booking(room=self.room, start=self.start, end=self.end, booker_name='   ')

        with self.assertRaises(ValidationError) as raised:
            booking.full_clean()

        self.assertIn('booker_name', raised.exception.message_dict)

    def test_deleting_the_room_deletes_its_bookings(self):
        room = make_room(name='Rivs')
        booking = make_booking(room, self.start, self.end)

        room.delete()

        self.assertFalse(Booking.objects.filter(pk=booking.pk).exists())

    def test_deleting_the_member_keeps_the_booking_without_an_author(self):
        member = make_member('booking-author')
        booking = make_booking(self.room, self.start, self.end, author=member)

        member.delete()
        booking.refresh_from_db()

        self.assertIsNone(booking.author)
        # The name is recorded when the booking is made, so deleting the
        # account does not erase who booked the room.
        self.assertEqual(booking.booker_name, 'booking-author')
        self.assertEqual(booking.booker_display, 'booking-author')

    def test_a_member_booking_records_the_booker_name(self):
        member = make_member('booking-snapshot')
        booking = make_booking(self.room, self.start, self.end, author=member)

        self.assertEqual(booking.booker_name, str(member))

    def test_a_name_typed_by_the_board_is_not_overwritten(self):
        member = make_member('booking-typed')
        booking = make_booking(self.room, self.start, self.end, author=member, booker_name='Ringde kansliet')

        self.assertEqual(booking.booker_name, 'Ringde kansliet')

    def test_the_snapshot_is_written_when_update_fields_is_narrow(self):
        # A save that names only the fields it changes must still carry the
        # snapshot, or the name stays in memory and is lost with the account.
        member = make_member('booking-narrow-update')
        booking = make_booking(self.room, self.start, self.end)
        booking.author = member

        booking.save(update_fields=['author'])

        self.assertEqual(Booking.objects.get(pk=booking.pk).booker_name, str(member))

    def test_an_empty_update_fields_is_still_a_no_op(self):
        # Django reads an empty update_fields as "write nothing"; the snapshot
        # must not turn that into a write of its own.
        member = make_member('booking-empty-update')
        booking = make_booking(self.room, self.start, self.end)
        booking.author = member

        booking.save(update_fields=[])

        stored = Booking.objects.get(pk=booking.pk)
        self.assertIsNone(stored.author_id)
        self.assertEqual(stored.booker_name, '')

    def test_an_empty_update_fields_generator_is_handled_like_an_empty_list(self):
        # Django reads any empty iterable as "write nothing". A generator has to
        # be consumed rather than left in kwargs, where save_base() cannot read
        # it and raises instead.
        member = make_member('booking-empty-generator')
        booking = make_booking(self.room, self.start, self.end)
        booking.author = member

        booking.save(update_fields=iter([]))

        stored = Booking.objects.get(pk=booking.pk)
        self.assertIsNone(stored.author_id)
        self.assertEqual(stored.booker_name, '')

    def test_a_write_nothing_save_does_not_consume_the_snapshot(self):
        # The name must not be filled in on the instance by a save that writes
        # nothing: the next narrow save would see it as already set, skip the
        # snapshot, and store an author with a blank name, which is the identity
        # loss the snapshot exists to prevent.
        member = make_member('booking-empty-then-narrow')
        booking = make_booking(self.room, self.start, self.end)
        booking.author = member

        booking.save(update_fields=[])
        booking.save(update_fields=['author'])

        stored = Booking.objects.get(pk=booking.pk)
        self.assertEqual(stored.author_id, member.pk)
        self.assertEqual(stored.booker_name, str(member))

    def test_a_new_booking_in_the_past_is_rejected(self):
        past = timezone.now() - datetime.timedelta(days=1)
        booking = Booking(room=self.room, start=past, end=past + datetime.timedelta(hours=1), booker_name='Någon')

        with self.assertRaises(ValidationError) as raised:
            booking.full_clean()

        self.assertIn('start', raised.exception.message_dict)

    def test_a_start_inside_the_grace_window_is_accepted(self):
        # A visitor filling the form by hand can be a few minutes late by the
        # time the POST lands, so a recent start is not treated as an error.
        recent = timezone.now() - BOOKING_PAST_GRACE / 2
        booking = Booking(
            room=self.room,
            start=recent,
            end=recent + datetime.timedelta(hours=1),
            booker_name='Någon',
        )

        booking.full_clean()

    def test_an_existing_booking_keeps_a_start_that_has_passed(self):
        # Otherwise the board could not correct the description of a booking
        # whose time is over without also being told its time is invalid.
        past = timezone.now() - datetime.timedelta(days=30)
        booking = make_booking(
            self.room,
            past,
            past + datetime.timedelta(hours=1),
            booker_name='Någon',
        )
        booking.refresh_from_db()
        booking.description = 'Rättad i efterhand'

        booking.full_clean()

    def test_booking_form_rejects_end_before_start(self):
        form = BookingForm(
            data={'start': local_input_time(self.end), 'end': local_input_time(self.start), 'description': ''},
            room=self.room,
            author=make_member('booking-form-author'),
        )

        self.assertFalse(form.is_valid())
        self.assertIn('end', form.errors)

    def test_booking_form_rejects_an_overlapping_submission(self):
        # SQLite ignores select_for_update, so the race itself cannot be tested
        # here; what is tested is that a duplicate overlapping submission is
        # rejected by validation instead of creating a second booking.
        make_booking(self.room, self.start, self.end)
        form = BookingForm(
            data={
                'start': local_input_time(self.start + datetime.timedelta(minutes=10)),
                'end': local_input_time(self.end + datetime.timedelta(minutes=10)),
                'description': '',
            },
            room=self.room,
            author=make_member('booking-form-clash'),
        )

        self.assertFalse(form.is_valid())
        self.assertIn('start', form.errors)

    def test_anonymous_form_requires_name_and_email(self):
        form = AnonymousBookingForm(
            data={'start': local_input_time(self.start), 'end': local_input_time(self.end), 'description': ''},
            room=self.room,
        )

        self.assertFalse(form.is_valid())
        self.assertIn('booker_name', form.errors)
        self.assertIn('booker_email', form.errors)


class BookingAvailabilityRulesTests(TestCase):
    """When a room may be booked: length, daily hours, closures."""

    def setUp(self):
        self.room = make_room(name='Bastun')
        self.start = timezone.localtime(timezone.now()).replace(second=0, microsecond=0) + datetime.timedelta(days=1)

    def booking(self, room=None, start=None, hours=1, **kwargs):
        start = start or self.start
        return Booking(
            room=room or self.room,
            start=start,
            end=start + datetime.timedelta(hours=hours),
            booker_name='Någon',
            **kwargs,
        )

    def test_a_booking_longer_than_a_week_is_refused(self):
        booking = self.booking(hours=24 * 8)

        with self.assertRaises(ValidationError) as raised:
            booking.full_clean()

        self.assertIn('end', raised.exception.message_dict)

    def test_a_booking_of_exactly_a_week_is_allowed(self):
        self.booking(hours=24 * 7).full_clean()

    def test_a_room_without_bookable_hours_takes_any_time_of_day(self):
        self.assertEqual(self.room.bookable_from, None)
        night = self.start.replace(hour=3)

        self.booking(start=night, hours=1).full_clean()

    def test_bookable_hours_refuse_a_booking_outside_them(self):
        self.room.bookable_from = datetime.time(8, 0)
        self.room.bookable_until = datetime.time(22, 0)
        self.room.save()

        with self.assertRaises(ValidationError) as raised:
            self.booking(start=self.start.replace(hour=3), hours=1).full_clean()

        self.assertIn('start', raised.exception.message_dict)
        # Inside the window is still fine, boundaries included.
        self.booking(start=self.start.replace(hour=8, minute=0), hours=1).full_clean()
        self.booking(start=self.start.replace(hour=21, minute=0), hours=1).full_clean()

    def test_bookable_hours_refuse_a_booking_that_runs_past_them(self):
        self.room.bookable_from = datetime.time(8, 0)
        self.room.bookable_until = datetime.time(22, 0)
        self.room.save()

        with self.assertRaises(ValidationError) as raised:
            self.booking(start=self.start.replace(hour=21, minute=0), hours=3).full_clean()

        self.assertIn('start', raised.exception.message_dict)

    def test_bookable_hours_refuse_a_booking_that_spans_the_closed_night(self):
        # 08:00 Monday to 20:00 Tuesday is inside the hours at both ends, and
        # still runs straight through the closed night, which is what a daily
        # window exists to prevent.
        self.room.bookable_from = datetime.time(8, 0)
        self.room.bookable_until = datetime.time(22, 0)
        self.room.save()
        monday = self.start.replace(hour=8, minute=0)
        tuesday = monday + datetime.timedelta(days=1)

        with self.assertRaises(ValidationError) as raised:
            Booking(
                room=self.room,
                start=monday,
                end=tuesday.replace(hour=20),
                booker_name='Någon',
            ).full_clean()

        self.assertIn('start', raised.exception.message_dict)

    def test_a_room_needs_both_hours_or_neither(self):
        self.room.bookable_from = datetime.time(8, 0)

        with self.assertRaises(ValidationError) as raised:
            self.room.full_clean()

        self.assertIn('bookable_until', raised.exception.message_dict)

    def test_the_closing_hour_must_be_after_the_opening_hour(self):
        self.room.bookable_from = datetime.time(22, 0)
        self.room.bookable_until = datetime.time(8, 0)

        with self.assertRaises(ValidationError) as raised:
            self.room.full_clean()

        self.assertIn('bookable_until', raised.exception.message_dict)

    def test_a_closure_blocks_a_booking_inside_it(self):
        closure = Closure.objects.create(
            room=self.room,
            start=self.start - datetime.timedelta(hours=1),
            end=self.start + datetime.timedelta(hours=1),
            description='Renovering',
        )

        with self.assertRaises(ValidationError) as raised:
            self.booking(hours=1).full_clean()

        self.assertIn('start', raised.exception.message_dict)
        # A closure is a period, so the booking just after it is still fine.
        self.booking(start=closure.end, hours=1).full_clean()

    def test_a_closure_in_another_room_does_not_block(self):
        other = make_room(name='Sauna')
        Closure.objects.create(
            room=other,
            start=self.start - datetime.timedelta(hours=1),
            end=self.start + datetime.timedelta(hours=1),
        )

        self.booking(hours=1).full_clean()

    def test_a_closure_must_end_after_it_starts(self):
        closure = Closure(room=self.room, start=self.start, end=self.start)

        with self.assertRaises(ValidationError) as raised:
            closure.full_clean()

        self.assertIn('end', raised.exception.message_dict)

    def test_the_closure_message_wins_over_the_double_booking_message(self):
        self.booking(hours=2).save()
        Closure.objects.create(room=self.room, start=self.start, end=self.start + datetime.timedelta(hours=1))

        with self.assertRaises(ValidationError) as raised:
            self.booking(hours=1).full_clean()

        # The closure is the better explanation of the two, so it is the one the
        # booker sees.
        self.assertIn('stängt', raised.exception.message_dict['start'][0])


class BookingAnonymousFlowTests(PinnedNowMixin, TestCase):
    """The visitor gate: readable pages, an unlock, a lockout and a booking."""

    def attempts(self):
        """Wrong codes this visitor has spent on this room."""
        return access.attempts_used(SimpleNamespace(session=self.client.session), self.room)

    def setUp(self):
        super().setUp()
        self.room = make_room(name='Bastun')
        self.room_url = reverse('booking:room_detail', args=[self.room.pk])
        self.index_url = reverse('booking:index')

    def current_code(self):
        return access.current_code(self.room)

    def wrong_code(self):
        accepted = set(access.accepted_codes(self.room, at=self.now))
        for candidate in ('000000', '111111', '222222', '333333', '999999'):
            if candidate not in accepted:
                return candidate
        raise AssertionError('no unused code candidate left')

    def unlock(self):
        response = self.client.post(self.room_url, {'code': self.current_code()})
        self.assertRedirects(response, self.room_url)
        return response

    def booking_payload(self, **overrides):
        start = self.now + datetime.timedelta(hours=1)
        end = start + datetime.timedelta(hours=1)
        payload = {
            'start': local_input_time(start),
            'end': local_input_time(end),
            'description': 'Bokad av besökare',
            'booker_name': 'Extern Besökare',
            'booker_email': 'besokare@example.com',
            'cf-turnstile-response': 'turnstile-token',
        }
        payload.update(overrides)
        return payload

    def test_room_list_is_readable_without_an_unlock(self):
        response = self.client.get(self.index_url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Bastun')

    def test_room_detail_renders_the_code_gate_without_an_unlock(self):
        response = self.client.get(self.room_url)

        self.assertEqual(response.status_code, 200)
        self.assertIn('code_form', response.context)
        self.assertNotIn('form', response.context)
        self.assertContains(response, 'Bastun')

    def test_public_pages_never_expose_the_code_or_the_booker(self):
        make_booking(
            self.room,
            self.now + datetime.timedelta(hours=2),
            self.now + datetime.timedelta(hours=3),
            booker_name='Hemlig Bokare',
            booker_email='hemlig@example.com',
            description='Hemlig beskrivning',
        )

        for url in (self.index_url, self.room_url):
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200)
                self.assertNotContains(response, self.current_code())
                self.assertNotContains(response, 'Hemlig Bokare')
                self.assertNotContains(response, 'hemlig@example.com')
                self.assertNotContains(response, 'Hemlig beskrivning')

    def test_posting_booking_data_without_an_unlock_creates_nothing(self):
        response = self.client.post(self.room_url, self.booking_payload())

        self.assertEqual(response.status_code, 403)
        self.assertFalse(Booking.objects.exists())
        # assertNotContains would insist on a 200, so read the gate body here.
        body = response.content.decode()
        self.assertNotIn('besokare@example.com', body)
        self.assertNotIn('Bokad av besökare', body)
        self.assertEqual(self.attempts(), 1)

    def test_empty_code_is_rejected_by_the_gate(self):
        response = self.client.post(self.room_url, {'code': ''})

        self.assertEqual(response.status_code, 403)
        self.assertNotIn(access.BOOKING_SESSION_TOKEN_KEY, self.client.session)

    def test_wrong_code_is_forbidden_and_counts_the_attempt(self):
        response = self.client.post(self.room_url, {'code': self.wrong_code()})

        self.assertEqual(response.status_code, 403)
        # A rejected attempt re-renders the form, but never the valid code.
        self.assertNotIn(self.current_code(), response.content.decode())
        self.assertEqual(self.attempts(), 1)

        response = self.client.post(self.room_url, {'code': self.wrong_code()})

        self.assertEqual(response.status_code, 403)
        self.assertEqual(self.attempts(), 2)
        self.assertNotIn(access.BOOKING_SESSION_TOKEN_KEY, self.client.session)

    def test_five_wrong_codes_lock_the_visitor_out(self):
        for _attempt in range(access.BOOKING_ATTEMPT_LIMIT):
            response = self.client.post(self.room_url, {'code': self.wrong_code()})

        self.assertEqual(response.status_code, 429)
        self.assertEqual(self.attempts(), access.BOOKING_ATTEMPT_LIMIT)
        self.assertIn(str(self.room.pk), self.client.session[access.BOOKING_LOCKOUT_UNTIL])

    def test_correct_code_during_a_lockout_is_still_locked(self):
        for _attempt in range(access.BOOKING_ATTEMPT_LIMIT):
            self.client.post(self.room_url, {'code': self.wrong_code()})

        response = self.client.post(self.room_url, {'code': self.current_code()})

        self.assertEqual(response.status_code, 429)
        self.assertNotIn(access.BOOKING_SESSION_TOKEN_KEY, self.client.session)

    def test_expired_lockout_clears_counters_and_shows_the_gate(self):
        for _attempt in range(access.BOOKING_ATTEMPT_LIMIT):
            self.client.post(self.room_url, {'code': self.wrong_code()})
        session = self.client.session
        session[access.BOOKING_LOCKOUT_UNTIL] = {str(self.room.pk): time.time() - 1}
        session.save()

        response = self.client.get(self.room_url)

        self.assertEqual(response.status_code, 200)
        self.assertIn('code_form', response.context)
        self.assertEqual(response.context['lockout_remaining'], 0)
        self.assertNotIn(access.BOOKING_ATTEMPTS_COUNTER, self.client.session)
        self.assertNotIn(access.BOOKING_LOCKOUT_UNTIL, self.client.session)

    def test_correct_code_redirects_and_stores_only_this_room_s_token(self):
        code = self.current_code()

        response = self.client.post(self.room_url, {'code': code})

        self.assertRedirects(response, self.room_url)
        stored = self.client.session[access.BOOKING_SESSION_TOKEN_KEY][str(self.room.pk)]
        self.assertEqual(stored, access.session_token(self.room))
        self.assertNotEqual(stored, code)
        self.assertNotIn(code, [str(value) for value in self.client.session.values()])

        unlocked = self.client.get(self.room_url)
        self.assertEqual(unlocked.status_code, 200)
        self.assertIn('form', unlocked.context)
        self.assertNotIn('code_form', unlocked.context)

    def test_unlocked_visitor_books_without_an_account(self):
        self.unlock()

        with patch('booking.views.validate_captcha', return_value=True):
            response = self.client.post(self.room_url, self.booking_payload())

        self.assertRedirects(response, self.room_url)
        booking = Booking.objects.get()
        self.assertIsNone(booking.author)
        self.assertTrue(booking.is_external)
        self.assertEqual(booking.booker_name, 'Extern Besökare')
        self.assertEqual(booking.booker_email, 'besokare@example.com')
        self.assertEqual(booking.room, self.room)

    def test_the_room_page_shows_a_closed_period_before_the_code_is_typed(self):
        # A visitor looking at the calendar should see why the room is
        # unavailable, not fill in the form and be refused afterwards.
        Closure.objects.create(
            room=self.room,
            start=self.now + datetime.timedelta(hours=2),
            end=self.now + datetime.timedelta(hours=5),
            description='Renovering',
        )

        response = self.client.get(self.room_url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Stängt')
        self.assertContains(response, 'Renovering')

    def test_a_booking_inside_a_closed_period_is_refused(self):
        self.unlock()
        start = self.now + datetime.timedelta(hours=1)
        Closure.objects.create(
            room=self.room,
            start=start - datetime.timedelta(minutes=30),
            end=start + datetime.timedelta(hours=2),
        )

        with patch('booking.views.validate_captcha', return_value=True):
            response = self.client.post(self.room_url, self.booking_payload())

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'stängt')
        self.assertFalse(Booking.objects.exists())

    def test_rotation_invalidates_an_existing_unlock(self):
        self.unlock()
        old_code = self.current_code()

        self.room.rotate_code(at=self.now)

        response = self.client.get(self.room_url)

        self.assertEqual(response.status_code, 200)
        self.assertIn('code_form', response.context)
        self.assertNotIn('form', response.context)
        # Rotating ends the unlock at once, while the code that was just handed
        # out keeps working for the grace window.
        self.assertTrue(access.check_code(self.room, old_code, at=self.now))
        self.assertEqual(self.client.post(self.room_url, {'code': old_code}).status_code, 302)

    def test_the_old_code_stops_working_when_the_grace_window_ends(self):
        self.unlock()
        old_code = self.current_code()
        self.room.rotate_code(at=self.now)

        # Move past the grace window without moving the moment the rotation
        # stamped: the room is the thing that holds it now.
        Room.objects.filter(pk=self.room.pk).update(
            rotated_at=self.now - access.BOOKING_CODE_GRACE - datetime.timedelta(minutes=1)
        )
        self.room.refresh_from_db()
        self.client.session.flush()

        response = self.client.post(self.room_url, {'code': old_code})

        self.assertEqual(response.status_code, 403)
        self.assertNotIn(access.BOOKING_SESSION_TOKEN_KEY, self.client.session)

    def test_the_unlock_is_stored_for_the_room_that_was_gated(self):
        # The view fetches the room once and hands the same instance to the code
        # check and to the unlock, so the token is filed under this room alone.
        code = self.current_code()

        response = self.client.post(self.room_url, {'code': code})

        self.assertRedirects(response, self.room_url, fetch_redirect_response=False)
        self.assertEqual(
            self.client.session[access.BOOKING_SESSION_TOKEN_KEY],
            {str(self.room.pk): access.session_token(self.room)},
        )
        # A different room's unlock is a different thing, which is what stops
        # one room's code from opening another.
        other = make_room(name='Sauna')
        self.assertFalse(access.session_has_access(SimpleNamespace(session=self.client.session), other))

    def test_a_rotation_landing_mid_request_cannot_unlock_the_new_generation(self):
        # The check and the grant work from one room instance, so a rotation that
        # lands between them leaves the visitor holding a token for the
        # generation whose code they actually typed. That token must not open the
        # room they have not got the new code for.
        room = self.room
        real_check = access.check_code

        def check_then_rotate(checked_room, candidate, at=None):
            accepted = real_check(checked_room, candidate, at=at)
            Room.objects.filter(pk=room.pk).update(code_generation=checked_room.code_generation + 1)
            return accepted

        code = self.current_code()
        with patch('booking.access.check_code', side_effect=check_then_rotate):
            response = self.client.post(self.room_url, {'code': code})

        self.assertRedirects(response, self.room_url, fetch_redirect_response=False)
        self.assertEqual(
            self.client.session[access.BOOKING_SESSION_TOKEN_KEY],
            {str(room.pk): access.session_token(room)},
        )

        room.refresh_from_db()
        self.assertEqual(room.code_generation, 2)
        gated_again = self.client.get(self.room_url)
        self.assertIn('code_form', gated_again.context)
        self.assertNotIn('form', gated_again.context)

    def test_captcha_failure_blocks_creation(self):
        self.unlock()

        with patch('booking.views.validate_captcha', return_value=False) as captcha:
            response = self.client.post(self.room_url, self.booking_payload())

        captcha.assert_called_once_with('turnstile-token')
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Booking.objects.exists())

    def test_the_gate_explains_the_code_without_naming_a_channel(self):
        # A visitor who has never booked before cannot guess that the code
        # exists or who holds it, so the page has to say so. It must not say how
        # the code reaches them: the board hands it out however it likes, and a
        # sentence promising email would be wrong for most of them.
        response = self.client.get(self.room_url)

        self.assertContains(response, 'Bokningskoden får du av styrelsen.')
        self.assertNotContains(response, 'får du av styrelsen via')

    def test_the_gate_shows_the_boards_own_instructions_when_set(self):
        # The board can say how the code is obtained, for example that it is
        # given out at the office, without a code change.
        settings_row = BookingSettings.get_solo()
        settings_row.code_instructions = 'Koden delas ut i kansliet på onsdagar.'
        settings_row.save()

        response = self.client.get(self.room_url)

        self.assertContains(response, 'Koden delas ut i kansliet på onsdagar.')
        self.assertNotContains(response, 'Bokningskoden får du av styrelsen.')
        # The fact about accounts still holds and is still shown.
        self.assertContains(response, 'behöver då ingen kod')

    def test_the_gate_explains_the_code_in_english_too(self):
        # The English page is what an outsider who does not read Swedish sees,
        # and it is the only place the catalogs for this feature are exercised.
        # Set through the cookie: the site's language middleware activates the
        # request language and would override translation.override().
        self.client.cookies[settings.LANGUAGE_COOKIE_NAME] = 'en'

        response = self.client.get(self.room_url)

        self.assertContains(response, 'You get the booking code from the board')

    def test_the_room_list_says_that_a_code_is_needed(self):
        response = self.client.get(self.index_url)

        self.assertContains(response, 'bokningskod, som du får av styrelsen')
        self.assertNotContains(response, 'får av styrelsen via')

    def test_the_booking_page_names_the_board_as_the_contact(self):
        self.unlock()

        response = self.client.get(self.room_url)

        self.assertContains(
            response,
            f'Har du frågor om en bokning, kontakta styrelsen via {settings.CONTENT_VARIABLES["ASSOCIATION_EMAIL"]}',
        )

    def test_a_booking_in_the_past_is_rejected(self):
        self.unlock()
        past = self.now - datetime.timedelta(days=1)

        with patch('booking.views.validate_captcha', return_value=True):
            response = self.client.post(
                self.room_url,
                self.booking_payload(
                    start=local_input_time(past),
                    end=local_input_time(past + datetime.timedelta(hours=1)),
                ),
            )

        self.assertEqual(response.status_code, 200)
        self.assertIn('start', response.context['form'].errors)
        self.assertFalse(Booking.objects.exists())


class BookingMemberFlowTests(TestCase):
    """A signed-in member needs no code step, only a valid booking."""

    def setUp(self):
        self.member = make_member('booking-member')
        self.client.force_login(self.member, backend='members.backends.AuthBackend')
        self.room = make_room(name='Bastun')
        self.room_url = reverse('booking:room_detail', args=[self.room.pk])

    def booking_payload(self, **overrides):
        start = timezone.now() + datetime.timedelta(days=1)
        end = start + datetime.timedelta(hours=1)
        payload = {'start': local_input_time(start), 'end': local_input_time(end), 'description': 'Medlemsbokning'}
        payload.update(overrides)
        return payload

    def test_member_sees_the_booking_form_without_the_code_gate(self):
        response = self.client.get(self.room_url)

        self.assertEqual(response.status_code, 200)
        self.assertIn('form', response.context)
        self.assertNotIn('code_form', response.context)

    def test_member_booking_is_stored_with_the_member_as_author(self):
        response = self.client.post(self.room_url, self.booking_payload())

        self.assertRedirects(response, self.room_url)
        booking = Booking.objects.get()
        self.assertEqual(booking.author, self.member)
        # The member's display name is snapshotted so the booking still says who
        # booked it after the account is deleted.
        self.assertEqual(booking.booker_name, str(self.member))
        self.assertFalse(booking.is_external)

    def test_member_booking_in_the_past_is_rejected(self):
        past = timezone.now() - datetime.timedelta(days=1)

        response = self.client.post(
            self.room_url,
            self.booking_payload(
                start=local_input_time(past),
                end=local_input_time(past + datetime.timedelta(hours=1)),
            ),
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn('start', response.context['form'].errors)
        self.assertFalse(Booking.objects.exists())

    def test_the_start_input_offers_the_same_range_the_model_accepts(self):
        # Pinned so the assertion cannot lose a race with the clock ticking over
        # to the next minute between the render and the comparison.
        pinned = timezone.localtime(timezone.now()).replace(second=0, microsecond=0)
        with patch('booking.access.now_at', new=lambda: pinned):
            response = self.client.get(self.room_url)

        # The input's floor is the model's grace boundary, not the current
        # moment: a floor of "now" would make the picker refuse a start that
        # Booking.clean() accepts, and would invalidate a start that was picked
        # a moment earlier if the form is re-rendered after another error.
        expected = timezone.localtime(pinned - BOOKING_PAST_GRACE).strftime('%Y-%m-%dT%H:%M')
        for name in ('start', 'end'):
            with self.subTest(field=name):
                self.assertEqual(response.context['form'].fields[name].widget.attrs['min'], expected)

    def test_captcha_is_not_consulted_for_members(self):
        with patch('booking.views.validate_captcha') as captcha:
            response = self.client.post(self.room_url, self.booking_payload())

        self.assertRedirects(response, self.room_url)
        captcha.assert_not_called()
        self.assertEqual(Booking.objects.count(), 1)

    def test_duplicate_overlapping_submission_is_rejected(self):
        self.client.post(self.room_url, self.booking_payload())

        response = self.client.post(self.room_url, self.booking_payload())

        self.assertEqual(response.status_code, 200)
        self.assertEqual(Booking.objects.count(), 1)
        self.assertIn('start', response.context['form'].errors)


class BookingAdminPermissionTests(TestCase):
    """Staff status is group-based; per-model permissions do the gating."""

    def setUp(self):
        self.room = make_room(name='Bastun')
        self.start = timezone.now() + datetime.timedelta(days=1)
        self.booking = make_booking(self.room, self.start, self.start + datetime.timedelta(hours=1))

    def _login(self, member):
        self.client.force_login(member, backend='members.backends.AuthBackend')

    def test_group_without_booking_permissions_is_denied_the_app(self):
        self.assertIn('fotograf', settings.STAFF_GROUPS)
        self._login(make_staff_member('booking-photographer', 'fotograf'))

        index = self.client.get(reverse('admin:index'))

        self.assertEqual(index.status_code, 200)
        for changelist in (
            reverse('admin:booking_room_changelist'),
            reverse('admin:booking_booking_changelist'),
        ):
            with self.subTest(changelist=changelist):
                self.assertNotContains(index, changelist)
                self.assertEqual(self.client.get(changelist).status_code, 403)

        self.assertEqual(self.client.get(reverse('admin:app_list', args=['booking'])).status_code, 404)

    def test_view_only_permission_can_read_but_not_write(self):
        self._login(make_staff_member('booking-viewer', settings.STAFF_GROUPS[0], (('booking', 'view_booking'),)))
        change_url = reverse('admin:booking_booking_change', args=[self.booking.pk])

        self.assertEqual(self.client.get(reverse('admin:booking_booking_changelist')).status_code, 200)
        self.assertEqual(self.client.get(reverse('admin:booking_booking_add')).status_code, 403)
        # A view-only holder gets the read-only change page, but no POST may
        # change anything.
        self.assertEqual(self.client.get(change_url).status_code, 200)
        self.assertEqual(self.client.post(change_url, {'room': self.room.pk, '_save': 'Spara'}).status_code, 403)
        delete_url = reverse('admin:booking_booking_delete', args=[self.booking.pk])
        self.assertEqual(self.client.get(delete_url).status_code, 403)

        self.assertEqual(Booking.objects.count(), 1)
        self.booking.refresh_from_db()
        self.assertEqual(self.booking.description, '')

    def test_editor_can_add_change_and_delete(self):
        self._login(
            make_staff_member(
                'booking-editor',
                settings.STAFF_GROUPS[0],
                (('booking', 'add_booking'), ('booking', 'change_booking'), ('booking', 'delete_booking')),
            )
        )
        add_url = reverse('admin:booking_booking_add')

        add_page = self.client.get(add_url)

        self.assertEqual(add_page.status_code, 200)
        self.assertContains(add_page, 'name="start_0"')

        start = self.start + datetime.timedelta(days=1)
        end = start + datetime.timedelta(hours=1)
        response = self.client.post(
            add_url,
            {
                'room': self.room.pk,
                'booker_name': 'Admin bokare',
                'booker_email': '',
                'description': 'Skapad i admin',
                'start_0': start.strftime('%Y-%m-%d'),
                'start_1': start.strftime('%H:%M:%S'),
                'end_0': end.strftime('%Y-%m-%d'),
                'end_1': end.strftime('%H:%M:%S'),
                '_save': 'Spara',
            },
        )

        self.assertEqual(response.status_code, 302)
        created = Booking.objects.get(description='Skapad i admin')

        response = self.client.post(
            reverse('admin:booking_booking_change', args=[created.pk]),
            {
                'room': self.room.pk,
                'booker_name': 'Admin bokare',
                'booker_email': '',
                'description': 'Ändrad i admin',
                'start_0': start.strftime('%Y-%m-%d'),
                'start_1': start.strftime('%H:%M:%S'),
                'end_0': end.strftime('%Y-%m-%d'),
                'end_1': end.strftime('%H:%M:%S'),
                '_save': 'Spara',
            },
        )

        self.assertEqual(response.status_code, 302)
        created.refresh_from_db()
        self.assertEqual(created.description, 'Ändrad i admin')

        response = self.client.post(reverse('admin:booking_booking_delete', args=[created.pk]), {'post': 'yes'})

        self.assertEqual(response.status_code, 302)
        self.assertFalse(Booking.objects.filter(pk=created.pk).exists())


class BookingAdminSurfaceTests(TestCase):
    """What the board actually sees: the order, the filters and the room page."""

    def setUp(self):
        self.room = make_room(name='Bastun')
        self.now = timezone.now()
        self.editor = make_staff_member(
            'booking-surface-editor',
            settings.STAFF_GROUPS[0],
            (
                ('booking', 'view_booking'),
                ('booking', 'view_room'),
                ('booking', 'view_bookingsettings'),
            ),
        )
        self.client.force_login(self.editor, backend='members.backends.AuthBackend')

    def _booking(self, **kwargs):
        start = kwargs.pop('start', self.now + datetime.timedelta(days=1))
        return make_booking(self.room, start, start + datetime.timedelta(hours=1), **kwargs)

    def _request(self, user=None, **data):
        request = RequestFactory().get('/admin/booking/booking/', data)
        request.user = user or self.editor
        return request

    def _time_label(self, booking):
        """The text the Tid column renders, which is what the row order is read from."""
        start = timezone.localtime(booking.start)
        end = timezone.localtime(booking.end)
        return f'{start:%Y-%m-%d %H:%M} - {end:%H:%M}'

    def test_the_changelist_opens_on_the_newest_booking_not_the_oldest(self):
        oldest = self._booking(start=self.now + datetime.timedelta(days=1))
        newest = self._booking(start=self.now + datetime.timedelta(days=30))

        body = self.client.get(reverse('admin:booking_booking_changelist')).content.decode()

        self.assertLess(body.index(self._time_label(newest)), body.index(self._time_label(oldest)))

    def _origin_filtered(self, query):
        """Apply the origin filter the way the changelist does.

        The changelist hands over ``dict(request.GET.lists())``, so every value
        is a list and the filter takes its last element.
        """
        params = {key: [value] for key, value in query.items()}
        request = self._request(**query)
        chosen = BookingOriginFilter(request, params, Booking, BookingAdmin(Booking, admin.site))
        return set(chosen.queryset(request, Booking.objects.all()).values_list('pk', flat=True))

    def test_the_origin_filter_separates_member_and_website_bookings(self):
        by_member = self._booking(author=self.editor)
        by_visitor = self._booking(booker_name='Extern Besökare', booker_email='besokare@example.com')
        # A booking whose member deleted the account: no author, and no address,
        # because the public form always records one.
        deleted_member = self._booking(booker_name='Före detta medlem')

        self.assertEqual(self._origin_filtered({'origin': 'account'}), {by_member.pk})
        self.assertEqual(self._origin_filtered({'origin': 'no_account'}), {by_visitor.pk, deleted_member.pk})
        self.assertEqual(self._origin_filtered({'origin': 'external'}), {by_visitor.pk})
        # An absent or unknown value must not filter anything out.
        self.assertEqual(self._origin_filtered({}), {by_member.pk, by_visitor.pk, deleted_member.pk})
        self.assertEqual(
            self._origin_filtered({'origin': 'nonsense'}), {by_member.pk, by_visitor.pk, deleted_member.pk}
        )

    def test_the_room_page_lists_upcoming_bookings_only(self):
        past = self._booking(start=self.now - datetime.timedelta(days=30))
        upcoming = self._booking(start=self.now + datetime.timedelta(days=2))
        model_admin = BookingInline(Booking, admin.site)

        listed = set(model_admin.get_queryset(self._request()).values_list('pk', flat=True))

        self.assertEqual(listed, {upcoming.pk})
        self.assertNotIn(past.pk, listed)

    def test_the_room_page_lists_upcoming_bookings_soonest_first(self):
        later = self._booking(start=self.now + datetime.timedelta(days=5))
        sooner = self._booking(start=self.now + datetime.timedelta(days=1))
        model_admin = BookingInline(Booking, admin.site)

        listed = list(model_admin.get_queryset(self._request()).values_list('pk', flat=True))

        self.assertEqual(listed, [sooner.pk, later.pk])

    def _inline_editor(self):
        """A board member who may change the room and its bookings from the room page."""
        editor = make_staff_member(
            'booking-inline-editor',
            settings.STAFF_GROUPS[0],
            (
                ('booking', 'change_room'),
                ('booking', 'view_booking'),
                ('booking', 'change_booking'),
                ('booking', 'delete_booking'),
            ),
        )
        self.client.force_login(editor, backend='members.backends.AuthBackend')
        return editor

    def _room_inline_post_data(self, booking, prefix, **extra):
        local_start = timezone.localtime(booking.start)
        local_end = timezone.localtime(booking.end)
        data = {
            f'{prefix}-TOTAL_FORMS': '1',
            f'{prefix}-INITIAL_FORMS': '1',
            f'{prefix}-MIN_NUM_FORMS': '0',
            f'{prefix}-MAX_NUM_FORMS': '1000',
            f'{prefix}-0-id': str(booking.pk),
            f'{prefix}-0-room': str(self.room.pk),
            f'{prefix}-0-start_0': local_start.strftime('%Y-%m-%d'),
            f'{prefix}-0-start_1': local_start.strftime('%H:%M:%S'),
            f'{prefix}-0-end_0': local_end.strftime('%Y-%m-%d'),
            f'{prefix}-0-end_1': local_end.strftime('%H:%M:%S'),
            f'{prefix}-0-booker_name': booking.booker_name,
            f'{prefix}-0-description': booking.description,
            f'{prefix}-0-author': '',
            'name': self.room.name,
            '_save': 'Spara',
        }
        data.update(extra)
        return data

    def _let_time_pass(self, booking):
        """Move a booking into the past, as the clock would while the page is open.

        Written with ``update()`` and then read back so the submitted form data
        carries the times the page would now show. ``end`` stays after ``start``
        to satisfy the database check constraint.
        """
        Booking.objects.filter(pk=booking.pk).update(
            start=self.now - datetime.timedelta(hours=2),
            end=self.now - datetime.timedelta(hours=1),
        )
        booking.refresh_from_db()
        return booking

    def test_a_row_that_ended_while_the_page_was_open_still_deletes(self):
        self._inline_editor()
        room_url = reverse('admin:booking_room_change', args=[self.room.pk])
        booking = self._booking(start=self.now + datetime.timedelta(hours=1), booker_name='Någon')
        # Read the prefix from the rendered page, which also proves the row was
        # shown to the board before its time passed.
        page = self.client.get(room_url).content.decode()
        prefix = re.search(r'name="([A-Za-z0-9_]+)-TOTAL_FORMS"', page).group(1)
        self.assertIn('Någon', page)

        # The end passes between the page being opened and the form being
        # submitted. The row has to stay in the inline's queryset: an id Django
        # cannot resolve becomes an unsaved instance, the checked delete is
        # dropped, and the save still reports success.
        booking = self._let_time_pass(booking)

        response = self.client.post(
            room_url,
            self._room_inline_post_data(booking, prefix, **{f'{prefix}-0-DELETE': 'on'}),
        )

        self.assertEqual(response.status_code, 302)
        self.assertFalse(Booking.objects.filter(pk=booking.pk).exists())

    def test_a_row_that_ended_while_the_page_was_open_still_saves(self):
        self._inline_editor()
        room_url = reverse('admin:booking_room_change', args=[self.room.pk])
        booking = self._booking(start=self.now + datetime.timedelta(hours=1), booker_name='Någon')
        page = self.client.get(room_url).content.decode()
        prefix = re.search(r'name="([A-Za-z0-9_]+)-TOTAL_FORMS"', page).group(1)

        booking = self._let_time_pass(booking)
        response = self.client.post(
            room_url,
            self._room_inline_post_data(booking, prefix, **{f'{prefix}-0-description': 'Ändrad i efterhand'}),
        )

        self.assertEqual(response.status_code, 302)
        booking.refresh_from_db()
        self.assertEqual(booking.description, 'Ändrad i efterhand')

    def test_another_inlines_ids_do_not_pull_rows_into_the_room_inline(self):
        # The preservation reads the submitted formset's own prefix, so a page
        # hosting a second inline cannot drag a stale booking back into view.
        past = self._booking(start=self.now - datetime.timedelta(days=1))
        request = RequestFactory().post(
            '/admin/booking/room/1/change/',
            {'other-0-id': str(past.pk), 'other-TOTAL_FORMS': '1'},
        )
        request.user = self.editor
        model_admin = BookingInline(Booking, admin.site)

        self.assertEqual(model_admin._submitted_pks(request), set())
        # Read the pks out: comparing an integer against a queryset of Booking
        # objects would pass whether or not the row were there.
        listed = list(model_admin.get_queryset(request).values_list('pk', flat=True))
        self.assertNotIn(past.pk, listed)

    def test_an_unparseable_id_is_ignored_rather_than_raising(self):
        # int() refuses a very long digit string and a superscript two, and a
        # stray id must not turn the room page into a 500 for whoever posted it.
        request = RequestFactory().post(
            '/admin/booking/room/1/change/',
            {
                'bookings-0-id': '9' * 5000,
                'bookings-1-id': '\u00b2',
                'bookings-2-id': 'abc',
                'bookings-other-0-id': '7',
                'bookings-3-unrelated-id': '8',
            },
        )
        request.user = self.editor

        self.assertEqual(BookingInline(Booking, admin.site)._submitted_pks(request), set())

    def test_the_sidebar_offers_booking_to_a_holder_of_the_permissions(self):
        # Asserted on the hrefs rather than on the group title: the labels are
        # translated, so the title depends on the active language.
        groups = get_sidebar_navigation(self._request())
        booking_groups = [
            group
            for group in groups
            if any(item['link'] == reverse('admin:booking_booking_changelist') for item in group['items'])
        ]

        self.assertEqual(len(booking_groups), 1)
        self.assertEqual(
            {item['link'] for item in booking_groups[0]['items']},
            {
                reverse('admin:booking_booking_changelist'),
                reverse('admin:booking_room_changelist'),
                reverse('admin:booking_bookingsettings_changelist'),
            },
        )

    def test_the_sidebar_hides_booking_from_a_group_without_the_permissions(self):
        photographer = make_staff_member('booking-surface-photographer', settings.STAFF_GROUPS[0])

        groups = get_sidebar_navigation(self._request(user=photographer))
        hrefs = {item['link'] for group in groups for item in group['items']}

        self.assertNotIn(reverse('admin:booking_booking_changelist'), hrefs)
        self.assertNotIn(reverse('admin:booking_room_changelist'), hrefs)


class BookingSettingsAdminTests(PinnedNowMixin, TestCase):
    """The settings row is now only the public note about getting a code."""

    def setUp(self):
        super().setUp()
        self.admin_user = get_user_model().objects.create_superuser(
            username='booking-admin',
            password='pwd',
            email='booking-admin@example.com',
        )
        self.client.force_login(self.admin_user)

    def test_singleton_refuses_a_second_row(self):
        booking_settings = BookingSettings.get_solo()
        add_url = reverse('admin:booking_bookingsettings_add')

        self.assertEqual(self.client.get(add_url).status_code, 403)
        self.assertEqual(self.client.post(add_url, {'code_instructions': 'nej'}).status_code, 403)

        self.assertEqual(BookingSettings.objects.count(), 1)
        booking_settings.refresh_from_db()
        self.assertEqual(booking_settings.code_instructions, '')

    def test_first_row_is_created_by_saving_the_add_form(self):
        BookingSettings.objects.all().delete()
        add_url = reverse('admin:booking_bookingsettings_add')

        response = self.client.get(add_url)

        # Rendering the add page must not store the row: doing so would flip
        # has_add_permission to False and refuse the POST the admin just filled
        # in with a 403.
        self.assertEqual(response.status_code, 200)
        self.assertFalse(BookingSettings.objects.exists())

        response = self.client.post(add_url, {'code_instructions': 'Fråga i kansliet.'})

        self.assertEqual(response.status_code, 302)
        self.assertEqual(BookingSettings.get_solo().code_instructions, 'Fråga i kansliet.')

    def test_singleton_refuses_deletion(self):
        booking_settings = BookingSettings.get_solo()
        delete_url = reverse('admin:booking_bookingsettings_delete', args=[booking_settings.pk])

        self.assertEqual(self.client.get(delete_url).status_code, 403)
        self.assertEqual(self.client.post(delete_url, {'post': 'yes'}).status_code, 403)
        self.assertTrue(BookingSettings.objects.filter(pk=booking_settings.pk).exists())

    def test_the_page_offers_only_the_note(self):
        # The codes moved to the rooms, so this page must not claim to have one.
        booking_settings = BookingSettings.get_solo()
        url = reverse('admin:booking_bookingsettings_change', args=[booking_settings.pk])

        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        form_fields = response.context['adminform'].form.fields
        self.assertEqual(list(form_fields), ['code_instructions'])
        self.assertContains(response, 'name="code_instructions"')
        self.assertNotContains(response, 'name="current_code"')
        self.assertNotContains(response, 'Byt bokningskoden nu')

    def test_the_board_can_write_how_a_code_is_handed_out(self):
        booking_settings = BookingSettings.get_solo()
        url = reverse('admin:booking_bookingsettings_change', args=[booking_settings.pk])

        response = self.client.post(url, {'code_instructions': 'Koden står på dörren till kansliet.'})

        self.assertEqual(response.status_code, 302)
        booking_settings.refresh_from_db()
        self.assertEqual(booking_settings.code_instructions, 'Koden står på dörren till kansliet.')


class RoomCodeAdminTests(PinnedNowMixin, TestCase):
    """Each room shows its own code, and the action rotates it for that room."""

    def setUp(self):
        super().setUp()
        self.admin_user = get_user_model().objects.create_superuser(
            username='room-code-admin',
            password='pwd',
            email='room-code-admin@example.com',
        )
        self.client.force_login(self.admin_user)
        self.office = make_room(name='Kansliet')
        self.sauna = make_room(name='Bastun')

    def inline_management_data(self):
        """The management form of every inline on the room page, with no rows.

        The room page carries both inlines, and a POST that leaves one of them
        out is refused rather than treated as empty.
        """
        data = {}
        for prefix in ('bookings', 'closures'):
            data.update(
                {
                    f'{prefix}-TOTAL_FORMS': '0',
                    f'{prefix}-INITIAL_FORMS': '0',
                    f'{prefix}-MIN_NUM_FORMS': '0',
                    f'{prefix}-MAX_NUM_FORMS': '1000',
                }
            )
        return data

    def test_the_changelist_shows_each_room_s_code(self):
        body = self.client.get(reverse('admin:booking_room_changelist')).content.decode()

        self.assertIn(access.current_code(self.office), body)
        self.assertIn(access.current_code(self.sauna), body)
        self.assertNotEqual(access.current_code(self.office), access.current_code(self.sauna))
        self.assertIn('Aldrig', body)

    def test_the_room_page_shows_the_code_and_when_it_was_rotated(self):
        url = reverse('admin:booking_room_change', args=[self.office.pk])
        self.assertContains(self.client.get(url), 'Aldrig')

        self.office.rotate_code(at=timezone.localtime(timezone.now()).replace(microsecond=0))
        rotated = formats.date_format(timezone.localtime(self.office.rotated_at), 'DATETIME_FORMAT')

        response = self.client.get(url)

        self.assertContains(response, access.current_code(self.office))
        self.assertContains(response, rotated)
        self.assertNotContains(response, 'Aldrig')

    def test_editing_a_room_does_not_put_a_stale_code_generation_back(self):
        # The race the guarded save exists for: the admin reads the room, the
        # board opens the page, somebody rotates the room from elsewhere, and the
        # save that follows must not undo that rotation. Rotating on the way in
        # is what makes this test fail if the guard is replaced with a plain
        # save(): the form was built from the pre-rotation row.
        url = reverse('admin:booking_room_change', args=[self.office.pk])
        real_get_object = RoomAdmin.get_object

        def rotate_after_the_read(admin_self, request, object_id, from_field=None):
            stale = real_get_object(admin_self, request, object_id, from_field)
            Room.objects.filter(pk=self.office.pk).update(code_generation=5, rotated_at=timezone.now())
            return stale

        with patch.object(RoomAdmin, 'get_object', rotate_after_the_read):
            response = self.client.post(
                url,
                {
                    'name': 'Kansliet (nytt namn)',
                    'description': '',
                    '_save': 'Spara',
                    **self.inline_management_data(),
                },
            )

        self.assertEqual(response.status_code, 302)
        self.office.refresh_from_db()
        # The edit landed...
        self.assertEqual(self.office.name, 'Kansliet (nytt namn)')
        # ...and the rotation that happened in the meantime survived it.
        self.assertEqual(self.office.code_generation, 5)
        self.assertIsNotNone(self.office.rotated_at)
        self.assertEqual(access.current_code(self.office), access.code_for_generation(self.office, 5))

    def test_a_room_can_still_be_created_from_the_admin(self):
        # The guarded save belongs to the change path only: an insert has no
        # primary key yet, and Django refuses update_fields without one.
        response = self.client.post(
            reverse('admin:booking_room_add'),
            {
                'name': 'Nytt utrymme',
                'description': 'Nytt',
                '_save': 'Spara',
                **self.inline_management_data(),
            },
        )

        self.assertEqual(response.status_code, 302)
        created = Room.objects.get(name='Nytt utrymme')
        self.assertEqual(created.code_generation, 1)
        self.assertIsNone(created.rotated_at)
        self.assertTrue(access.current_code(created).isdigit())

    def test_the_rotate_action_hands_out_a_new_code_for_the_selected_room(self):
        old_code = access.current_code(self.office)
        sauna_code = access.current_code(self.sauna)

        response = self.client.post(
            reverse('admin:booking_room_changelist'),
            {
                'action': 'rotate_code',
                '_selected_action': [str(self.office.pk)],
                'index': '0',
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.office.refresh_from_db()
        self.assertEqual(self.office.code_generation, 2)
        new_code = access.current_code(self.office)
        self.assertNotEqual(new_code, old_code)
        # The message names the room, because the board may rotate several at
        # once and has to know which code belongs to which room.
        told = [str(message) for message in response.context['messages']]
        self.assertTrue(any('Kansliet' in message and new_code in message for message in told), told)
        # The room that was not selected is untouched.
        self.sauna.refresh_from_db()
        self.assertEqual(self.sauna.code_generation, 1)
        self.assertEqual(access.current_code(self.sauna), sauna_code)

    def test_the_rotate_action_is_hidden_from_a_view_only_holder(self):
        old_code = access.current_code(self.office)
        viewer = make_staff_member(
            'room-code-viewer',
            settings.STAFF_GROUPS[0],
            (('booking', 'view_room'),),
        )
        self.client.force_login(viewer, backend='members.backends.AuthBackend')

        response = self.client.post(
            reverse('admin:booking_room_changelist'),
            {
                'action': 'rotate_code',
                '_selected_action': [str(self.office.pk)],
                'index': '0',
            },
            follow=True,
        )

        # Django drops an action the user may not run and re-renders the list
        # with a warning rather than a 403, so what has to hold is that the code
        # did not move and the action was never offered.
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'Byt bokningskoden nu')
        self.office.refresh_from_db()
        self.assertEqual(self.office.code_generation, 1)
        self.assertEqual(access.current_code(self.office), old_code)


class BookingEmailTests(PinnedNowMixin, TestCase):
    """Only an external booker with an address gets a confirmation."""

    def setUp(self):
        super().setUp()
        self.room = make_room(name='Bastun')
        self.room_url = reverse('booking:room_detail', args=[self.room.pk])

    def attempts(self):
        """Wrong codes this visitor has spent on this room."""
        return access.attempts_used(SimpleNamespace(session=self.client.session), self.room)

    def unlock(self):
        response = self.client.post(self.room_url, {'code': access.current_code(self.room)})
        self.assertRedirects(response, self.room_url)

    def booking_payload(self):
        start = self.now + datetime.timedelta(hours=1)
        end = start + datetime.timedelta(hours=1)
        return {
            'start': local_input_time(start),
            'end': local_input_time(end),
            'description': 'E-posttest',
            'booker_name': 'Extern Besökare',
            'booker_email': 'besokare@example.com',
            'cf-turnstile-response': 'turnstile-token',
        }

    def test_external_booking_queues_exactly_one_confirmation(self):
        self.unlock()

        with patch('booking.views.validate_captcha', return_value=True):
            with patch('booking.emails.send_email_task') as send_email:
                with self.captureOnCommitCallbacks(execute=True):
                    response = self.client.post(self.room_url, self.booking_payload())

        self.assertEqual(response.status_code, 302)
        send_email.delay.assert_called_once()
        _subject, _body, from_email, recipients = send_email.delay.call_args.args
        self.assertEqual(recipients, ['besokare@example.com'])
        self.assertEqual(from_email, settings.DEFAULT_FROM_EMAIL)

    def test_the_confirmation_tells_the_booker_how_to_reach_the_board(self):
        # The email is the only durable record an outside booker has, and the
        # board is the only route to change or cancel the booking.
        booking = make_booking(
            self.room,
            self.now + datetime.timedelta(hours=1),
            self.now + datetime.timedelta(hours=2),
            booker_name='Extern Besökare',
            booker_email='besokare@example.com',
        )

        with patch('booking.emails.send_email_task') as send_email:
            with self.captureOnCommitCallbacks(execute=True):
                emails.notify_external_booker(booking)

        _subject, body, _from_email, _recipients = send_email.delay.call_args.args
        self.assertIn(settings.CONTENT_VARIABLES['ASSOCIATION_EMAIL'], body)

    def test_member_booking_queues_no_confirmation(self):
        member = make_member('booking-email-member')
        self.client.force_login(member, backend='members.backends.AuthBackend')

        with patch('booking.emails.send_email_task') as send_email:
            with self.captureOnCommitCallbacks(execute=True):
                response = self.client.post(self.room_url, self.booking_payload())

        self.assertEqual(response.status_code, 302)
        send_email.delay.assert_not_called()
        self.assertEqual(Booking.objects.get().author, member)

    def test_blank_booker_email_queues_no_confirmation(self):
        start = self.now + datetime.timedelta(hours=1)
        booking = make_booking(
            self.room,
            start,
            start + datetime.timedelta(hours=1),
            booker_name='Extern utan adress',
            booker_email='',
        )

        with patch('booking.emails.send_email_task') as send_email:
            with self.captureOnCommitCallbacks(execute=True):
                emails.notify_external_booker(booking)

        self.assertTrue(booking.is_external)
        send_email.delay.assert_not_called()


class BookingGateRegressionTests(PinnedNowMixin, TestCase):
    """Regressions for defects found while integrating the gate.

    Each of these failed before its fix: a non-ASCII code raised TypeError out
    of ``hmac.compare_digest`` (a server error instead of a rejected code), the
    lockout message printed the raw seconds count as minutes, and the admin time
    column formatted the stored UTC value instead of local time.
    """

    def setUp(self):
        super().setUp()
        booking_settings = BookingSettings.get_solo()
        booking_settings.save()
        self.room = make_room(name='Kansliet')
        self.room_url = reverse('booking:room_detail', args=[self.room.pk])

    def wrong_code(self):
        accepted = set(access.accepted_codes(self.room, at=self.now))
        for candidate in ('000000', '111111', '222222'):
            if candidate not in accepted:
                return candidate
        raise AssertionError('no unused code candidate left')

    def test_non_ascii_code_is_rejected_instead_of_raising(self):
        current = access.current_code(self.room)

        self.assertFalse(access.check_code(self.room, 'å' * access.BOOKING_CODE_DIGITS, at=self.now))
        self.assertFalse(access.check_code(self.room, 'KOD123', at=self.now))
        self.assertTrue(access.check_code(self.room, current, at=self.now))

    def test_non_ascii_code_post_is_rejected_by_the_gate(self):
        response = self.client.post(self.room_url, {'code': 'å' * access.BOOKING_CODE_DIGITS})

        self.assertEqual(response.status_code, 403)
        self.assertNotIn(access.BOOKING_SESSION_TOKEN_KEY, self.client.session)

    def test_lockout_message_reports_minutes_not_seconds(self):
        for _attempt in range(access.BOOKING_ATTEMPT_LIMIT):
            self.client.post(self.room_url, {'code': self.wrong_code()})

        response = self.client.get(self.room_url)

        self.assertEqual(response.status_code, 429)
        self.assertEqual(response.context['lockout_minutes'], access.BOOKING_LOCKOUT_SECONDS // 60)
        # The visible message has to be in minutes, and must not print the raw
        # seconds count as a minute count.
        self.assertContains(response, '15 minuter', status_code=429)
        self.assertNotIn(str(access.BOOKING_LOCKOUT_SECONDS), response.content.decode())

    def test_admin_time_column_renders_local_time(self):
        start = timezone.localtime(self.now).replace(microsecond=0)
        end = start + datetime.timedelta(hours=1)
        booking = make_booking(self.room, start, end, booker_name='Någon')
        # create() keeps the value it was handed in memory, so read the stored
        # one back before comparing against the column.
        booking.refresh_from_db()
        model_admin = BookingAdmin(Booking, admin.site)
        local = f'{timezone.localtime(booking.start):%Y-%m-%d %H:%M} - {timezone.localtime(booking.end):%H:%M}'
        raw = f'{booking.start:%Y-%m-%d %H:%M} - {booking.end:%H:%M}'

        self.assertEqual(model_admin.time_range(booking), local)
        self.assertEqual(model_admin.time_range(booking), f'{start:%Y-%m-%d %H:%M} - {end:%H:%M}')
        # Formatting the stored value directly would print UTC whenever the
        # timezone has a non-zero offset, which is the regression this pins.
        if raw != local:
            self.assertNotEqual(model_admin.time_range(booking), raw)


class BookingGateCaptchaTests(PinnedNowMixin, TestCase):
    """The gate asks for the captcha before it looks at the code.

    The attempt counter and the lockout live in the session, so a client that
    discards the cookie is never limited. Requiring the captcha on the code form
    is what makes each guess cost a challenge; it fails open when no Turnstile
    secret is configured, which is why the other classes here can post a code
    without one.
    """

    def attempts(self):
        """Wrong codes this visitor has spent on this room."""
        return access.attempts_used(SimpleNamespace(session=self.client.session), self.room)

    def setUp(self):
        super().setUp()
        booking_settings = BookingSettings.get_solo()
        booking_settings.save()
        self.room = make_room(name='Kansliet')
        self.room_url = reverse('booking:room_detail', args=[self.room.pk])

    def current_code(self):
        return access.current_code(self.room)

    def accepted_codes(self):
        return set(access.accepted_codes(self.room, at=self.now))

    def wrong_code(self):
        for candidate in ('000000', '111111', '222222'):
            if candidate not in self.accepted_codes():
                return candidate
        raise AssertionError('no unused code candidate left')

    def test_the_gate_renders_the_captcha_widget_and_its_script(self):
        response = self.client.get(self.room_url)

        self.assertContains(response, 'cf-turnstile')
        self.assertContains(response, 'turnstile/v0/api.js')

    def test_a_failed_captcha_never_inspects_the_submitted_code(self):
        with patch('booking.access.validate_captcha', return_value=False):
            with patch('booking.access.check_code') as check_code:
                response = self.client.post(self.room_url, {'code': self.current_code()})

        self.assertEqual(response.status_code, 403)
        check_code.assert_not_called()

    @staticmethod
    def normalised_body(response):
        # The CSRF token is a fresh random mask on every render, so drop its
        # value before comparing two responses body for body.
        return re.sub(rb'name="csrfmiddlewaretoken" value="[^"]*"', b'csrf', response.content)

    def test_a_failed_captcha_does_not_reveal_whether_the_code_was_right(self):
        with patch('booking.access.validate_captcha', return_value=False):
            right = self.client.post(self.room_url, {'code': self.current_code()})
        after_right = dict(self.client.session)
        with patch('booking.access.validate_captcha', return_value=False):
            wrong = self.client.post(self.room_url, {'code': self.wrong_code()})
        after_wrong = dict(self.client.session)

        # Any difference here, for example a "Fel kod." shown only for the wrong
        # guess, would let an unverified client learn the code one guess at a
        # time without ever passing the challenge. Status, body and session
        # effects all have to be indistinguishable.
        self.assertEqual(right.status_code, 403)
        self.assertEqual(wrong.status_code, 403)
        self.assertEqual(self.normalised_body(right), self.normalised_body(wrong))
        self.assertEqual(after_right, after_wrong)
        self.assertNotIn(access.BOOKING_ATTEMPTS_COUNTER, after_wrong)
        self.assertNotIn(access.BOOKING_SESSION_TOKEN_KEY, after_wrong)

    def test_a_rejected_challenge_does_not_revoke_an_existing_unlock(self):
        with patch('booking.access.validate_captcha', return_value=True):
            self.client.post(self.room_url, {'code': self.current_code()})

        with patch('booking.access.validate_captcha', return_value=False):
            response = self.client.post(self.room_url, {'code': self.wrong_code()})

        self.assertEqual(response.status_code, 403)
        # The unlock survives, so a booker who submits a stale code form from an
        # older tab is not thrown back to the gate.
        served = self.client.get(self.room_url)
        self.assertIn('form', served.context)
        self.assertNotIn('code_form', served.context)

    def test_a_code_and_booking_payload_together_is_handled_by_the_gate(self):
        with patch('booking.access.validate_captcha', return_value=True):
            response = self.client.post(
                self.room_url,
                {
                    'code': self.current_code(),
                    'booker_name': 'Försök',
                    'booker_email': 'forsok@example.com',
                },
            )

        self.assertRedirects(response, self.room_url)
        self.assertFalse(Booking.objects.exists())

    def test_an_accepted_challenge_with_a_wrong_code_counts_an_attempt(self):
        with patch('booking.access.validate_captcha', return_value=True):
            response = self.client.post(self.room_url, {'code': self.wrong_code()})

        self.assertEqual(response.status_code, 403)
        self.assertEqual(self.attempts(), 1)
        self.assertNotIn(access.BOOKING_SESSION_TOKEN_KEY, self.client.session)

    def test_a_failed_captcha_is_reported_and_is_not_a_code_attempt(self):
        with patch('booking.access.validate_captcha', return_value=False):
            response = self.client.post(self.room_url, {'code': self.current_code()})

        self.assertEqual(response.status_code, 403)
        self.assertContains(response, 'Kunde inte verifiera', status_code=403)
        self.assertNotIn(access.BOOKING_SESSION_TOKEN_KEY, self.client.session)
        self.assertNotIn(access.BOOKING_ATTEMPTS_COUNTER, self.client.session)

    def test_the_validator_receives_the_submitted_token(self):
        with patch('booking.access.validate_captcha', return_value=True) as captcha:
            self.client.post(self.room_url, {'code': self.current_code(), 'cf-turnstile-response': 'token-123'})

        captcha.assert_called_once_with('token-123')

    def test_a_missing_captcha_token_is_normalised_to_an_empty_string(self):
        # core.utils.validate_captcha only short-circuits on "", so passing None
        # would send a verification request to Cloudflare for every request that
        # simply omits the field.
        with patch('booking.access.validate_captcha', return_value=False) as captcha:
            self.client.post(self.room_url, {'code': self.current_code()})

        captcha.assert_called_once_with('')

    def test_a_passed_captcha_unlocks(self):
        with patch('booking.access.validate_captcha', return_value=True):
            response = self.client.post(self.room_url, {'code': self.current_code()})

        self.assertRedirects(response, self.room_url)
        self.assertIn(access.BOOKING_SESSION_TOKEN_KEY, self.client.session)

    def test_a_stale_code_submission_is_gated_even_when_already_unlocked(self):
        with patch('booking.access.validate_captcha', return_value=True):
            self.client.post(self.room_url, {'code': self.current_code()})
        self.assertIn(access.BOOKING_SESSION_TOKEN_KEY, self.client.session)

        with patch('booking.access.validate_captcha', return_value=True):
            response = self.client.post(self.room_url, {'code': self.current_code()})

        # Handled by the gate (a redirect), not by the booking form (a 200 with
        # errors about booking fields the visitor never filled in).
        self.assertRedirects(response, self.room_url)
