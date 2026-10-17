"""Tests for the booking confirmation mail and the calendar invite it carries.

The sending code renders both templates and builds the invite from one fixed
context, so what is pinned here is the presentation: what the booker reads in
the body, and what a calendar client reads in the attached file. The invite is
tested as text, because that is what it is and how a client parses it.
"""

import datetime
import re
import zoneinfo
from unittest.mock import patch

from django.template.loader import render_to_string
from django.test import SimpleTestCase

from booking.ics import ATTACHMENT_MIMETYPE, booking_invite, invite_attachment
from booking.models import Booking, Room

# Pinned so the rendered weekday and the UTC bounds do not follow the machine the
# suite runs on. October 7 is still summer time in Helsinki, so 18:00 local is
# 15:00 UTC.
HELSINKI = zoneinfo.ZoneInfo('Europe/Helsinki')
START = datetime.datetime(2026, 10, 7, 18, 0, tzinfo=HELSINKI)
END = datetime.datetime(2026, 10, 7, 20, 0, tzinfo=HELSINKI)
START_UTC = '20261007T150000Z'
END_UTC = '20261007T170000Z'

HTML_TEMPLATE = 'booking/email/booking_confirmation.html'
TEXT_TEMPLATE = 'booking/email/booking_confirmation.txt'


def make_booking(**overrides):
    """An unsaved booking: rendering a mail needs no row behind it."""
    fields = {
        'pk': 7,
        'room': Room(pk=1, name='Bastun'),
        'start': START,
        'end': END,
        'booker_name': 'Någon',
        'description': 'Repetition',
    }
    fields.update(overrides)
    return Booking(**fields)


def mail_context(booking, **overrides):
    values = {
        'booking': booking,
        'room': booking.room,
        'start_local': booking.start,
        'end_local': booking.end,
        'cancel_url': 'https://date.example/booking/cancel/',
        'cancel_code': 'abc123def456',
        'association_email': 'styrelsen@example.com',
        'site_url': 'https://date.example/',
    }
    values.update(overrides)
    return values


def render_body(template, **overrides):
    booking = overrides.pop('booking', make_booking())
    return render_to_string(template, mail_context(booking, **overrides))


def unfold(content):
    """The invite's content lines as a client sees them, with folds joined."""
    return content.replace('\r\n ', '')


def property_value(content, name):
    """The unfolded value of one property line."""
    prefix = f'{name}:'
    for line in unfold(content).split('\r\n'):
        if line.startswith(prefix):
            return line[len(prefix) :]
    raise AssertionError(f'the invite has no {name}')


def escaped(value):
    """The escaping RFC 5545 asks of a TEXT value, spelled out here so a break
    in the module's own escaping cannot hide behind its own helper."""
    return (
        value.replace('\\', '\\\\')
        .replace('\r\n', '\\n')
        .replace('\n', '\\n')
        .replace('\r', '\\n')
        .replace(';', '\\;')
        .replace(',', '\\,')
    )


class BookingInviteTests(SimpleTestCase):
    """The attached file, read the way a calendar client reads it."""

    def build(self, *, cancel_url='', **overrides):
        booking = make_booking(**overrides)
        content = booking_invite(
            booking=booking,
            room=booking.room,
            start=booking.start,
            end=booking.end,
            cancel_url=cancel_url,
        )
        return booking, content

    def test_one_published_event_with_the_times_in_utc(self):
        _booking, content = self.build()
        lines = unfold(content).split('\r\n')

        self.assertEqual(lines[0], 'BEGIN:VCALENDAR')
        self.assertTrue(content.endswith('END:VCALENDAR\r\n'))
        self.assertIn('VERSION:2.0', lines)
        self.assertIn('METHOD:PUBLISH', lines)
        self.assertTrue(any(line.startswith('PRODID:') for line in lines))
        self.assertEqual(sum(line == 'BEGIN:VEVENT' for line in lines), 1)
        self.assertEqual(sum(line == 'END:VEVENT' for line in lines), 1)
        self.assertEqual(property_value(content, 'DTSTART'), START_UTC)
        self.assertEqual(property_value(content, 'DTEND'), END_UTC)
        self.assertEqual(property_value(content, 'SUMMARY'), 'Bastun')
        self.assertIn('STATUS:CONFIRMED', lines)
        self.assertRegex(property_value(content, 'DTSTAMP'), r'^\d{8}T\d{6}Z$')

    def test_every_line_ends_with_crlf(self):
        _booking, content = self.build()

        self.assertNotIn('\n', content.replace('\r\n', ''))
        self.assertNotIn('\r', content.replace('\r\n', ''))

    def test_a_long_non_ascii_description_folds_within_75_octets(self):
        # Two-byte letters throughout, so folding on character count would hand
        # a client lines past the limit, and a fold between the halves of one
        # letter would corrupt it.
        description = ('Återkommande övning med styrelsen och övriga intresserade. ' * 4).strip()
        _booking, content = self.build(description=description)

        for line in content.split('\r\n'):
            self.assertLessEqual(len(line.encode('utf-8')), 75, line)
        # A fold happened at all, and unfolding restores the value byte for byte.
        self.assertIn('\r\n ', content)
        self.assertEqual(property_value(content, 'DESCRIPTION'), escaped(description))

    def test_semicolons_commas_and_newlines_are_escaped(self):
        _booking, content = self.build(description='Rad ett; med komma, och\nen andra rad')

        self.assertEqual(
            property_value(content, 'DESCRIPTION'),
            'Rad ett\\; med komma\\, och\\nen andra rad',
        )

    def test_the_uid_is_stable_and_belongs_to_one_booking(self):
        booking, content = self.build()
        uid = property_value(content, 'UID')

        # A re-sent invite has to land on the same event, so neither a corrected
        # time nor another site address may move the UID.
        other_booking, other_content = self.build(
            pk=8,
            start=START + datetime.timedelta(hours=1),
            end=END + datetime.timedelta(hours=1),
            cancel_url='https://other.example/',
        )
        self.assertEqual(
            uid,
            property_value(
                booking_invite(
                    booking=booking,
                    room=booking.room,
                    start=booking.start + datetime.timedelta(hours=2),
                    end=booking.end + datetime.timedelta(hours=2),
                    cancel_url='https://elsewhere.example/',
                ),
                'UID',
            ),
        )
        self.assertIn(str(booking.pk), uid)
        self.assertNotEqual(uid, property_value(other_content, 'UID'))

    def test_the_site_address_becomes_the_url_and_the_cancellation_hint(self):
        _booking, without = self.build(cancel_url='')
        _booking, with_site = self.build(cancel_url='https://date.example')

        self.assertNotIn('URL:', unfold(without))
        self.assertNotIn('avbokas', unfold(without))
        self.assertEqual(property_value(with_site, 'URL'), 'https://date.example')
        self.assertEqual(
            property_value(with_site, 'DESCRIPTION'),
            'Repetition\\nBokningen kan avbokas på https://date.example.',
        )

    def test_the_invite_asks_the_booker_for_no_response(self):
        # An invite that looks like it came from a person makes clients offer a
        # reply nobody reads, so there is nobody to accept or decline.
        _booking, content = self.build()

        for property_name in ('ATTENDEE', 'ORGANIZER', 'VALARM'):
            self.assertNotIn(property_name, content)

    def test_invite_attachment_returns_the_file_triple(self):
        booking = make_booking()

        # The clock is pinned across both generations. DTSTAMP comes from
        # timezone.now(), so comparing a file generated now with one generated a
        # moment later fails whenever the second boundary falls between them.
        with patch('booking.ics.timezone.now', return_value=booking.start):
            filename, content, mimetype = invite_attachment(
                booking=booking,
                room=booking.room,
                start=booking.start,
                end=booking.end,
            )
            expected = booking_invite(
                booking=booking,
                room=booking.room,
                start=booking.start,
                end=booking.end,
            )

        self.assertEqual(filename, f'booking-{booking.pk}.ics')
        self.assertTrue(filename.endswith('.ics'))
        self.assertEqual(mimetype, 'text/calendar; method=PUBLISH; charset=utf-8')
        self.assertEqual(mimetype, ATTACHMENT_MIMETYPE)
        self.assertIn('BEGIN:VCALENDAR', content)
        self.assertEqual(content, expected)


class BookingConfirmationBodyTests(SimpleTestCase):
    """The two bodies the sender renders from the same context."""

    def test_the_html_body_names_the_room_the_time_and_the_code(self):
        html = render_body(HTML_TEMPLATE)

        self.assertIn('Bastun', html)
        self.assertIn('18:00', html)
        self.assertIn('20:00', html)
        self.assertIn('abc123def456', html)
        self.assertIn('Spara koden. Den behövs för att avboka bokningen.', html)
        self.assertIn('https://date.example/booking/cancel/', html)

    def test_the_text_body_carries_the_same_facts_without_markup(self):
        text = render_body(TEXT_TEMPLATE)

        self.assertIn('Bastun', text)
        self.assertIn('18:00', text)
        self.assertIn('20:00', text)
        self.assertIn('abc123def456', text)
        self.assertIn('Avbokningskod:', text)
        self.assertIn('https://date.example/booking/cancel/', text)
        self.assertNotIn('<', text)

    def test_an_end_on_another_day_is_named_in_both_bodies(self):
        booking = make_booking(end=datetime.datetime(2026, 10, 8, 9, 0, tzinfo=HELSINKI))

        for template in (HTML_TEMPLATE, TEXT_TEMPLATE):
            with self.subTest(template=template):
                body = render_body(template, booking=booking)
                self.assertIn('8.10', body)
                self.assertIn('09:00', body)

    def test_a_member_gets_no_code_and_cancels_from_the_account(self):
        for template in (HTML_TEMPLATE, TEXT_TEMPLATE):
            with self.subTest(template=template):
                body = render_body(template, cancel_code=None)
                self.assertIn('Logga in på Mina bokningar och ta bort bokningen där.', body)
                self.assertIn('https://date.example/booking/cancel/', body)
                self.assertNotIn('abc123def456', body)
                # A code exists only for a booker without an account, so the
                # word itself never reaches a member.
                self.assertNotIn('kod', body.lower())

    def test_the_description_typed_by_the_booker_is_shown_when_there_is_one(self):
        for template in (HTML_TEMPLATE, TEXT_TEMPLATE):
            with self.subTest(template=template):
                self.assertIn('Repetition', render_body(template))

    def test_a_booking_without_a_description_shows_no_description_line(self):
        for template in (HTML_TEMPLATE, TEXT_TEMPLATE):
            with self.subTest(template=template):
                body = render_body(template, booking=make_booking(description=''))
                self.assertNotIn('Beskrivning', body)
                self.assertNotIn('Repetition', body)

    def test_an_empty_association_address_leaves_no_dangling_sentence(self):
        for template in (HTML_TEMPLATE, TEXT_TEMPLATE):
            with self.subTest(template=template):
                body = render_body(template, association_email='')
                self.assertIn('Har du frågor om bokningen, kontakta styrelsen.', body)
                self.assertNotIn('kontakta styrelsen via', body)

    def test_a_set_association_address_is_shown(self):
        for template in (HTML_TEMPLATE, TEXT_TEMPLATE):
            with self.subTest(template=template):
                body = render_body(template)
                self.assertIn('kontakta styrelsen via styrelsen@example.com.', body)

    def test_the_body_survives_a_context_with_nothing_optional_set(self):
        # The narrowest context the sender can produce: no description, no
        # address, no code, no cancel page and no site address.
        empty = {
            'booking': make_booking(description=''),
            'cancel_url': '',
            'cancel_code': None,
            'association_email': '',
            'site_url': '',
        }

        for template in (HTML_TEMPLATE, TEXT_TEMPLATE):
            with self.subTest(template=template):
                body = render_body(template, **empty)
                self.assertIn('Bastun', body)
                self.assertIn('Om tiden inte passar', body)
                self.assertIn('Kontakta styrelsen om du vill avboka bokningen.', body)
                self.assertNotIn('None', body)
                self.assertNotIn('href=""', body)

    def test_the_html_body_carries_its_own_styling_and_the_site_colours(self):
        # Email clients strip <style> and never load an external sheet or an
        # image, so the look has to live in inline styles.
        html = render_body(HTML_TEMPLATE)

        self.assertNotIn('<style', html)
        self.assertNotIn('<script', html)
        self.assertNotIn('<img', html)
        self.assertNotIn('http://', html)
        self.assertIn('#202020', html)
        self.assertIn('rgb(208, 255, 0)', html)
        self.assertIn('max-width: 600px', html)

    def test_both_bodies_say_why_the_mail_was_sent(self):
        sentence = 'Du får det här meddelandet för att du bokade ett utrymme.'

        for template in (HTML_TEMPLATE, TEXT_TEMPLATE):
            with self.subTest(template=template):
                self.assertIn(sentence, render_body(template))

    def test_the_text_body_leaves_no_html_tag_behind(self):
        text = render_body(TEXT_TEMPLATE)

        self.assertIsNone(re.search(r'</?[a-zA-Z][^>]*>', text))
