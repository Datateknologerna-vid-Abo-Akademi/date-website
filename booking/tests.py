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
from types import SimpleNamespace
from unittest.mock import patch

from django.conf import settings
from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.core.exceptions import ValidationError
from django.test import RequestFactory, SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from django.utils import formats, timezone

from booking import access, emails
from booking.admin import BookingAdmin, BookingInline, BookingOriginFilter
from booking.forms import AnonymousBookingForm, BookingForm
from booking.models import BOOKING_PAST_GRACE, Booking, BookingSettings, Room
from core.admin_ui import get_sidebar_navigation

# Unsaved singletons: every settings-reading function in booking.access accepts
# one, so the pure-function tests need no database at all.
FIRST_CODE_SETTINGS = BookingSettings(code_generation=1)
SECOND_CODE_SETTINGS = BookingSettings(code_generation=2)

# core.settings.test pins SECRET_KEY to the literal "SECRET_KEY". These are the
# codes derived from it for the first generations, pinned so a change to the
# derivation (secret, message shape, digest truncation) fails loudly instead of
# silently handing every booker a different code.
PINNED_FIRST_CODE = '862536'
PINNED_SECOND_CODE = '623957'
PINNED_THIRD_CODE = '222378'


def local_input_time(value):
    """Return the value a ``datetime-local`` input submits."""
    return timezone.localtime(value).strftime('%Y-%m-%dT%H:%M')


def make_room(name='Bastun', is_active=True):
    return Room.objects.create(name=name, is_active=is_active)


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
    """The code is derived from the secret and a stored generation, never stored."""

    def setUp(self):
        super().setUp()
        self.at = datetime.datetime(2026, 3, 18, 15, 30)

    def test_code_is_six_digits_and_different_for_each_generation(self):
        codes = [access.code_for_generation(generation) for generation in range(1, 6)]

        for code in codes:
            self.assertEqual(len(code), access.BOOKING_CODE_DIGITS)
            self.assertTrue(code.isdigit())
        # A derivation that ignored the generation would hand out one code
        # forever, which is the failure this pins.
        self.assertEqual(len(set(codes)), len(codes))

    def test_the_known_generations_are_pinned(self):
        self.assertEqual(access.code_for_generation(1), PINNED_FIRST_CODE)
        self.assertEqual(access.code_for_generation(2), PINNED_SECOND_CODE)
        self.assertEqual(access.code_for_generation(3), PINNED_THIRD_CODE)

    def test_the_code_does_not_depend_on_the_clock(self):
        # The point of the change: nothing about the code moves on its own, so
        # no schedule has to run and a forgotten code stays valid.
        for at in (
            datetime.datetime(2026, 1, 5, 9, 0),
            datetime.datetime(2031, 7, 1, 3, 0),
            datetime.datetime(1999, 12, 31, 23, 59),
        ):
            with self.subTest(at=at), patch('booking.access.now_at', new=lambda at=at: at):
                self.assertEqual(access.current_code(access_settings=FIRST_CODE_SETTINGS), PINNED_FIRST_CODE)

    def test_current_code_follows_the_stored_generation(self):
        self.assertEqual(access.current_code(access_settings=FIRST_CODE_SETTINGS), PINNED_FIRST_CODE)
        self.assertEqual(access.current_code(access_settings=SECOND_CODE_SETTINGS), PINNED_SECOND_CODE)

    def test_code_is_identical_for_another_association(self):
        # The derivation uses SECRET_KEY and the generation only. Two
        # associations sharing a secret share codes, which is why the docs tell
        # each release to set its own.
        date_code = access.current_code(access_settings=FIRST_CODE_SETTINGS)

        with self.settings(PROJECT_NAME='kk'):
            other_code = access.current_code(access_settings=FIRST_CODE_SETTINGS)

        self.assertEqual(other_code, date_code)

    def test_a_different_secret_gives_a_different_code(self):
        with self.settings(SECRET_KEY='another-secret'):
            self.assertNotEqual(access.code_for_generation(1), PINNED_FIRST_CODE)


class BookingCodeRotationTests(TestCase):
    """Rotating is the only thing that moves the code, and it is deliberate."""

    def test_rotating_moves_to_the_next_generation_and_stamps_the_moment(self):
        settings_row = BookingSettings.get_solo()
        self.assertEqual(settings_row.code_generation, 1)
        self.assertIsNone(settings_row.rotated_at)
        before = access.current_code(access_settings=settings_row)

        at = timezone.now()
        generation = settings_row.rotate_code(at=at)

        self.assertEqual(generation, 2)
        settings_row.refresh_from_db()
        self.assertEqual(settings_row.code_generation, 2)
        self.assertEqual(settings_row.rotated_at, at)
        self.assertNotEqual(access.current_code(access_settings=settings_row), before)

    def test_rotating_twice_moves_twice(self):
        settings_row = BookingSettings.get_solo()

        settings_row.rotate_code()
        settings_row.rotate_code()

        self.assertEqual(settings_row.code_generation, 3)
        self.assertEqual(
            access.current_code(access_settings=settings_row),
            access.code_for_generation(3),
        )

    def test_rotating_ends_every_existing_unlock_at_once(self):
        # Deliberate asymmetry: the code just handed out keeps working for the
        # grace window, but an unlock granted with the old code does not.
        request = SimpleNamespace(session={})
        settings_row = BookingSettings.get_solo()
        access.grant_session(request, access_settings=settings_row)
        self.assertTrue(access.session_has_access(request, access_settings=settings_row))

        settings_row.rotate_code()

        self.assertFalse(access.session_has_access(request, access_settings=settings_row))

    def test_the_settings_row_is_created_with_the_first_generation(self):
        self.assertFalse(BookingSettings.objects.exists())

        settings_row = BookingSettings.get_solo()

        self.assertEqual(settings_row.code_generation, 1)
        self.assertIsNone(settings_row.rotated_at)


class BookingCodeGraceTests(SimpleTestCase):
    """The previous code keeps working briefly after the board rotates it.

    The window is anchored to the moment of the rotation, and a grant made
    during it stores the current generation's token, so an unlock cannot outlive
    the rotation that granted it.
    """

    def setUp(self):
        super().setUp()
        self.rotated_at = datetime.datetime(2026, 1, 5, 9, 0)
        self.after_rotation = BookingSettings(
            code_generation=2,
            rotated_at=timezone.make_aware(self.rotated_at, timezone.get_current_timezone()),
        )
        self.current_code = access.code_for_generation(2)
        self.previous_code = access.code_for_generation(1)

    def test_previous_code_is_accepted_just_after_the_rotation(self):
        at = self.rotated_at + datetime.timedelta(minutes=5)

        self.assertEqual(
            access.accepted_codes(at=at, access_settings=self.after_rotation),
            (self.current_code, self.previous_code),
        )
        self.assertTrue(access.check_code(self.previous_code, at=at, access_settings=self.after_rotation))

    def test_previous_code_is_rejected_after_the_grace_window(self):
        at = self.rotated_at + access.BOOKING_CODE_GRACE + datetime.timedelta(minutes=1)

        self.assertEqual(access.accepted_codes(at=at, access_settings=self.after_rotation), (self.current_code,))
        self.assertFalse(access.check_code(self.previous_code, at=at, access_settings=self.after_rotation))
        self.assertTrue(access.check_code(self.current_code, at=at, access_settings=self.after_rotation))

    def test_there_is_no_grace_before_anything_has_been_rotated(self):
        # The first code has no predecessor to keep alive, and a code that was
        # never handed out must not be accepted.
        fresh = BookingSettings(code_generation=1, rotated_at=None)

        self.assertEqual(
            access.accepted_codes(at=self.rotated_at, access_settings=fresh),
            (access.code_for_generation(1),),
        )

    def test_a_rotation_stamped_in_the_future_does_not_open_the_window(self):
        # Clock skew between app servers must not revive the previous code.
        at = self.rotated_at - datetime.timedelta(minutes=1)

        self.assertEqual(access.accepted_codes(at=at, access_settings=self.after_rotation), (self.current_code,))

    def test_grant_during_grace_stores_the_current_generation_token(self):
        request = SimpleNamespace(session={})

        access.grant_session(request, access_settings=self.after_rotation)

        stored = request.session[access.BOOKING_SESSION_TOKEN_KEY]
        self.assertEqual(stored, access.session_token(access_settings=self.after_rotation))
        self.assertNotEqual(stored, access.session_token(access_settings=FIRST_CODE_SETTINGS))
        # The unlocked visitor keeps access for as long as the generation holds,
        # and loses it the moment the board rotates again.
        self.assertTrue(access.session_has_access(request, access_settings=self.after_rotation))
        self.assertFalse(access.session_has_access(request, access_settings=FIRST_CODE_SETTINGS))


class BookingCodeValidationTests(SimpleTestCase):
    """An empty code is never accepted, so a blank gate cannot unlock."""

    def setUp(self):
        super().setUp()
        self.at = datetime.datetime(2026, 1, 5, 12, 0)

    def test_empty_code_is_never_accepted(self):
        for candidate in ('', None, '   '):
            with self.subTest(candidate=candidate):
                self.assertFalse(access.check_code(candidate, at=self.at, access_settings=FIRST_CODE_SETTINGS))

        # Positive control: the loop above must not pass vacuously.
        self.assertTrue(
            access.check_code(
                access.current_code(access_settings=FIRST_CODE_SETTINGS),
                at=self.at,
                access_settings=FIRST_CODE_SETTINGS,
            )
        )

    def test_short_or_stretched_codes_are_rejected(self):
        code = access.current_code(access_settings=FIRST_CODE_SETTINGS)

        self.assertFalse(access.check_code(code[:-1], at=self.at, access_settings=FIRST_CODE_SETTINGS))
        self.assertFalse(access.check_code(f'{code}0', at=self.at, access_settings=FIRST_CODE_SETTINGS))


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


class BookingAnonymousFlowTests(PinnedNowMixin, TestCase):
    """The visitor gate: readable pages, an unlock, a lockout and a booking."""

    def setUp(self):
        super().setUp()
        self.room = make_room(name='Bastun')
        self.room_url = reverse('booking:room_detail', args=[self.room.pk])
        self.index_url = reverse('booking:index')

    def current_code(self):
        return access.current_code()

    def wrong_code(self):
        accepted = set(access.accepted_codes(at=self.now))
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
        self.assertEqual(self.client.session[access.BOOKING_ATTEMPTS_COUNTER], 1)

    def test_empty_code_is_rejected_by_the_gate(self):
        response = self.client.post(self.room_url, {'code': ''})

        self.assertEqual(response.status_code, 403)
        self.assertNotIn(access.BOOKING_SESSION_TOKEN_KEY, self.client.session)

    def test_wrong_code_is_forbidden_and_counts_the_attempt(self):
        response = self.client.post(self.room_url, {'code': self.wrong_code()})

        self.assertEqual(response.status_code, 403)
        # A rejected attempt re-renders the form, but never the valid code.
        self.assertNotIn(self.current_code(), response.content.decode())
        self.assertEqual(self.client.session[access.BOOKING_ATTEMPTS_COUNTER], 1)

        response = self.client.post(self.room_url, {'code': self.wrong_code()})

        self.assertEqual(response.status_code, 403)
        self.assertEqual(self.client.session[access.BOOKING_ATTEMPTS_COUNTER], 2)
        self.assertNotIn(access.BOOKING_SESSION_TOKEN_KEY, self.client.session)

    def test_five_wrong_codes_lock_the_visitor_out(self):
        for _attempt in range(access.BOOKING_ATTEMPT_LIMIT):
            response = self.client.post(self.room_url, {'code': self.wrong_code()})

        self.assertEqual(response.status_code, 429)
        self.assertEqual(self.client.session[access.BOOKING_ATTEMPTS_COUNTER], access.BOOKING_ATTEMPT_LIMIT)
        self.assertIn(access.BOOKING_LOCKOUT_UNTIL, self.client.session)

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
        session[access.BOOKING_LOCKOUT_UNTIL] = time.time() - 1
        session.save()

        response = self.client.get(self.room_url)

        self.assertEqual(response.status_code, 200)
        self.assertIn('code_form', response.context)
        self.assertEqual(response.context['lockout_remaining'], 0)
        self.assertNotIn(access.BOOKING_ATTEMPTS_COUNTER, self.client.session)
        self.assertNotIn(access.BOOKING_LOCKOUT_UNTIL, self.client.session)

    def test_correct_code_redirects_and_stores_only_the_slot_token(self):
        code = self.current_code()

        response = self.client.post(self.room_url, {'code': code})

        self.assertRedirects(response, self.room_url)
        stored = self.client.session[access.BOOKING_SESSION_TOKEN_KEY]
        self.assertEqual(stored, access.session_token())
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

    def test_rotation_invalidates_an_existing_unlock(self):
        self.unlock()
        old_code = self.current_code()

        settings_row = BookingSettings.get_solo()
        settings_row.rotate_code(at=self.now)

        response = self.client.get(self.room_url)

        self.assertEqual(response.status_code, 200)
        self.assertIn('code_form', response.context)
        self.assertNotIn('form', response.context)
        # Rotating ends the unlock at once, while the code that was just handed
        # out keeps working for the grace window.
        self.assertTrue(access.check_code(old_code, at=self.now, access_settings=settings_row))
        self.assertEqual(self.client.post(self.room_url, {'code': old_code}).status_code, 302)

    def test_the_old_code_stops_working_when_the_grace_window_ends(self):
        self.unlock()
        old_code = self.current_code()
        settings_row = BookingSettings.get_solo()
        settings_row.rotate_code(at=self.now)

        # Move past the grace window without moving the stored moment.
        settings_row.rotated_at = self.now - access.BOOKING_CODE_GRACE - datetime.timedelta(minutes=1)
        settings_row.save(update_fields=['rotated_at'])
        self.client.session.flush()

        response = self.client.post(self.room_url, {'code': old_code})

        self.assertEqual(response.status_code, 403)
        self.assertNotIn(access.BOOKING_SESSION_TOKEN_KEY, self.client.session)

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

    def test_inactive_room_is_absent_from_the_list_and_404s(self):
        inactive = make_room(name='Stängt utrymme', is_active=False)

        listing = self.client.get(reverse('booking:index'))

        self.assertEqual(listing.status_code, 200)
        self.assertNotContains(listing, 'Stängt utrymme')
        self.assertEqual(self.client.get(reverse('booking:room_detail', args=[inactive.pk])).status_code, 404)


@override_settings(ROOT_URLCONF='core.urls.demo', BOOKING_ENABLED=False)
class BookingCapabilityDisabledTests(TestCase):
    """The capability hides the pages without uninstalling the app.

    core/urls/date.py includes the booking routes only while BOOKING_ENABLED is
    on; core.urls.demo is a urlconf built without them, which is what every
    other association ships.
    """

    def test_booking_pages_are_not_routed_when_the_capability_is_off(self):
        room = make_room(name='Bastun')

        self.assertEqual(self.client.get('/booking/').status_code, 404)
        self.assertEqual(self.client.get(f'/booking/{room.pk}/').status_code, 404)


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
            'is_active': 'on',
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
    """The settings are a singleton that only displays the derived code."""

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
        self.assertEqual(booking_settings.code_generation, 1)
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
        created = BookingSettings.get_solo()
        self.assertEqual(created.code_instructions, 'Fråga i kansliet.')
        self.assertEqual(created.code_generation, 1)

    def test_singleton_refuses_deletion(self):
        booking_settings = BookingSettings.get_solo()
        delete_url = reverse('admin:booking_bookingsettings_delete', args=[booking_settings.pk])

        self.assertEqual(self.client.get(delete_url).status_code, 403)
        self.assertEqual(self.client.post(delete_url, {'post': 'yes'}).status_code, 403)
        self.assertTrue(BookingSettings.objects.filter(pk=booking_settings.pk).exists())

    def test_change_page_shows_the_code_read_only_and_keeps_the_note_editable(self):
        booking_settings = BookingSettings.get_solo()
        url = reverse('admin:booking_bookingsettings_change', args=[booking_settings.pk])

        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        form_fields = response.context['adminform'].form.fields
        self.assertIn('code_instructions', form_fields)
        self.assertNotIn('current_code', form_fields)
        self.assertNotIn('last_rotated', form_fields)
        self.assertNotIn('code_generation', form_fields)
        self.assertNotIn('rotated_at', form_fields)
        self.assertContains(response, 'name="code_instructions"')
        self.assertNotContains(response, 'name="current_code"')
        self.assertNotContains(response, 'name="rotated_at"')

        code = access.current_code(access_settings=booking_settings)
        # A value the board reads rather than edits, rendered next to its own
        # label rather than on a class name that only one admin theme emits:
        # Unfold renders readonly values in a different container from the
        # classic admin, and the CI matrix runs both.
        self.assertRegex(html, f'Aktuell bokningskod[\\s\\S]{{0,400}}?{re.escape(code)}')

    def test_the_change_page_says_when_the_code_was_last_rotated(self):
        booking_settings = BookingSettings.get_solo()
        url = reverse('admin:booking_bookingsettings_change', args=[booking_settings.pk])
        self.assertContains(self.client.get(url), 'Aldrig')

        booking_settings.rotate_code(at=timezone.localtime(timezone.now()).replace(microsecond=0))
        rotated = formats.date_format(timezone.localtime(booking_settings.rotated_at), 'DATETIME_FORMAT')

        response = self.client.get(url)

        self.assertContains(response, rotated)
        self.assertNotContains(response, 'Aldrig')

    def test_the_board_can_write_how_the_code_is_handed_out(self):
        booking_settings = BookingSettings.get_solo()
        url = reverse('admin:booking_bookingsettings_change', args=[booking_settings.pk])

        response = self.client.get(url)
        self.assertContains(response, 'name="code_instructions"')

        response = self.client.post(
            url,
            {'code_instructions': 'Koden står på dörren till kansliet.'},
        )

        self.assertEqual(response.status_code, 302)
        booking_settings.refresh_from_db()
        self.assertEqual(booking_settings.code_instructions, 'Koden står på dörren till kansliet.')

    def test_the_rotate_action_hands_out_a_new_code(self):
        booking_settings = BookingSettings.get_solo()
        old_code = access.current_code(access_settings=booking_settings)
        changelist = reverse('admin:booking_bookingsettings_changelist')

        response = self.client.post(
            changelist,
            {
                'action': 'rotate_code',
                '_selected_action': [str(booking_settings.pk)],
                'index': '0',
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        booking_settings.refresh_from_db()
        self.assertEqual(booking_settings.code_generation, 2)
        new_code = access.current_code(access_settings=booking_settings)
        self.assertNotEqual(new_code, old_code)
        # The board has to be told the new code, because it is not stored anywhere
        # they could look it up later out of band.
        self.assertContains(response, new_code)

    def test_the_rotate_action_is_hidden_from_a_view_only_holder(self):
        booking_settings = BookingSettings.get_solo()
        viewer = make_staff_member(
            'booking-settings-viewer',
            settings.STAFF_GROUPS[0],
            (('booking', 'view_bookingsettings'),),
        )
        self.client.force_login(viewer, backend='members.backends.AuthBackend')

        response = self.client.post(
            reverse('admin:booking_bookingsettings_changelist'),
            {
                'action': 'rotate_code',
                '_selected_action': [str(booking_settings.pk)],
                'index': '0',
            },
            follow=True,
        )

        # Django drops an action the user may not run and re-renders the list
        # with a warning rather than a 403, so what has to hold is that the code
        # did not move and the action was never offered.
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'Byt bokningskoden nu')
        booking_settings.refresh_from_db()
        self.assertEqual(booking_settings.code_generation, 1)


class BookingEmailTests(PinnedNowMixin, TestCase):
    """Only an external booker with an address gets a confirmation."""

    def setUp(self):
        super().setUp()
        self.room = make_room(name='Bastun')
        self.room_url = reverse('booking:room_detail', args=[self.room.pk])

    def unlock(self):
        response = self.client.post(self.room_url, {'code': access.current_code()})
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
        accepted = set(access.accepted_codes(at=self.now))
        for candidate in ('000000', '111111', '222222'):
            if candidate not in accepted:
                return candidate
        raise AssertionError('no unused code candidate left')

    def test_non_ascii_code_is_rejected_instead_of_raising(self):
        current = access.current_code()

        self.assertFalse(access.check_code('å' * access.BOOKING_CODE_DIGITS, at=self.now))
        self.assertFalse(access.check_code('KOD123', at=self.now))
        self.assertTrue(access.check_code(current, at=self.now))

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

    def setUp(self):
        super().setUp()
        booking_settings = BookingSettings.get_solo()
        booking_settings.save()
        self.room = make_room(name='Kansliet')
        self.room_url = reverse('booking:room_detail', args=[self.room.pk])

    def current_code(self):
        return access.current_code()

    def accepted_codes(self):
        return set(access.accepted_codes(at=self.now))

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
        self.assertEqual(self.client.session[access.BOOKING_ATTEMPTS_COUNTER], 1)
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
