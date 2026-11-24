"""Guard the compact admin inline rule.

Unfold renders the object's name in a full-width line above every tabular
inline row. When the inline has a change link that line carries it; otherwise
it only repeats a field and every row pays the height. Inlines without a
change link use ``CompactTabularInline`` (or set ``show_title = False``), and
this test keeps a new inline from quietly reintroducing the tall row.
"""

from django import forms
from django.conf import settings
from django.contrib import admin
from django.test import TestCase
from django.urls import reverse

from booking.admin import BookingInline, ClosureInline
from booking.models import Booking, Closure
from events.admin import (
    EventAttendeesClassicInline,
    EventAttendeesFormInline,
    EventRegistrationFormClassicInline,
    EventRegistrationFormInline,
)
from publications.admin import PublicationClassicInline


class CompactTabularInlineTests(TestCase):
    def test_tabular_inlines_without_a_change_link_drop_the_title_row(self):
        offenders = []
        tabular_inlines = []
        for model, model_admin in admin.site._registry.items():
            for inline in model_admin.inlines:
                if not issubclass(inline, admin.TabularInline):
                    continue
                tabular_inlines.append(inline)
                if getattr(inline, 'show_change_link', False):
                    continue
                if getattr(inline, 'show_title', True):
                    offenders.append(f'{model._meta.label}.{inline.__name__}')

        self.assertTrue(tabular_inlines, 'Expected to inspect registered tabular inlines.')
        self.assertEqual(
            offenders,
            [],
            'These tabular inlines render an extra title row: use CompactTabularInline or set show_title = False.',
        )

    def test_event_inlines_are_compact(self):
        # The themed admin gives each attendee and each registration field a
        # collapsible block, so neither needs the repeated table title row.
        self.assertTrue(EventAttendeesFormInline.collapsible)
        self.assertTrue(EventRegistrationFormInline.collapsible)
        # The stock admin keeps both as compact tables.
        self.assertTrue(issubclass(EventAttendeesClassicInline, admin.TabularInline))
        self.assertTrue(issubclass(EventRegistrationFormClassicInline, admin.TabularInline))


class BookingDescriptionWidgetTests(TestCase):
    """Long descriptions must not be clipped into an 80 pixel input."""

    def test_booking_and_closure_are_stacked_blocks(self):
        for inline_class in (BookingInline, ClosureInline):
            with self.subTest(inline=inline_class.__name__):
                self.assertTrue(issubclass(inline_class, admin.StackedInline))
                self.assertFalse(issubclass(inline_class, admin.TabularInline))

    def test_classic_publications_are_stacked_blocks(self):
        # A stored filename and the redirect URL made the stock table wider
        # than the change form, which put the access flags and delete control
        # out of view.
        self.assertTrue(issubclass(PublicationClassicInline, admin.StackedInline))
        self.assertFalse(issubclass(PublicationClassicInline, admin.TabularInline))

    def test_booking_and_closure_descriptions_render_as_textareas(self):
        for inline_class, model in ((BookingInline, Booking), (ClosureInline, Closure)):
            with self.subTest(inline=inline_class.__name__):
                inline = inline_class(model, admin.site)
                formfield = inline.formfield_for_dbfield(model._meta.get_field('description'), None)

                self.assertIsInstance(formfield.widget, forms.Textarea)
                self.assertEqual(formfield.widget.attrs.get('rows'), 3)


class CollapsibleInlineTests(TestCase):
    """Inline blocks that hold several fields stay as collapsed summaries."""

    def test_room_disclosures_use_native_buttons_only_in_unfold(self):
        from datetime import timedelta

        from django.utils import timezone

        from booking.models import Room
        from members.models import Member

        user = Member.objects.create_superuser(
            username='inline-auditor', email='inline-auditor@example.invalid', password=None
        )
        self.client.force_login(user)
        room = Room.objects.create(name='Audit room')
        start = timezone.now() + timedelta(days=1)
        Booking.objects.create(room=room, start=start, end=start + timedelta(hours=1), title='Audit booking')

        response = self.client.get(reverse('admin:booking_room_change', args=[room.pk]))

        self.assertEqual(response.status_code, 200)
        if settings.USE_UNFOLD:
            self.assertNotContains(response, 'core/js/stock_admin_inlines.js')
            self.assertInHTML(
                '<button type="button" class="inline-disclosure-toggle" aria-expanded="false" '
                'x-bind:aria-expanded="openRow ? \'true\' : \'false\'" x-on:click="openRow = !openRow">'
                f'<strong class="font-semibold select-none">{Booking.objects.get().get_inline_title()}</strong>'
                '</button>',
                response.content.decode(),
            )
        else:
            self.assertNotContains(response, 'inline-disclosure-toggle')
            self.assertContains(response, 'core/css/stock_admin_inlines.css')
            self.assertContains(response, 'core/js/stock_admin_inlines.js')

    def test_blocks_that_need_space_are_collapsible(self):
        from booking.admin import BookingInline, ClosureInline
        from ctf.admin import FlagInline
        from staticpages.admin import UrlInline

        for inline_class in (BookingInline, ClosureInline, UrlInline, FlagInline):
            with self.subTest(inline=inline_class.__name__):
                self.assertTrue(getattr(inline_class, 'collapsible', False))

    def test_collapsed_booking_titles_show_the_period_and_title(self):
        from datetime import datetime, timedelta

        from django.utils import timezone

        from booking.models import Booking, Room

        room = Room(name='Audit room')
        start = timezone.make_aware(datetime(2026, 5, 1, 18, 0))
        booking = Booking(room=room, start=start, end=start + timedelta(hours=3), title='Styrelsemöte')

        title = booking.get_inline_title()

        self.assertNotIn(room.name, title)
        self.assertIn('18:00', title)
        self.assertIn('Styrelsemöte', title)

    def test_collapsed_booking_title_falls_back_to_the_booker(self):
        from datetime import datetime, timedelta

        from django.utils import timezone

        from booking.models import Booking, Room

        room = Room(name='Audit room')
        start = timezone.make_aware(datetime(2026, 5, 1, 18, 0))
        booking = Booking(room=room, start=start, end=start + timedelta(hours=3), booker_name='Albin Bäck')

        self.assertIn('Albin Bäck', booking.get_inline_title())

    def test_collapsed_closure_title_shows_the_reason(self):
        from datetime import datetime, timedelta

        from django.utils import timezone

        from booking.models import Closure, Room

        room = Room(name='Audit room')
        start = timezone.make_aware(datetime(2026, 5, 1, 8, 0))
        closure = Closure(room=room, start=start, end=start + timedelta(days=2), description='Renovering av golvet')

        title = closure.get_inline_title()

        self.assertNotIn(room.name, title)
        self.assertIn('Renovering av golvet', title)
