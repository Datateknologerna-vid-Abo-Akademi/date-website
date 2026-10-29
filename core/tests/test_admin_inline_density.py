"""Guard the compact admin inline rule.

Unfold renders the object's name in a full-width line above every tabular
inline row. When the inline has a change link that line carries it; otherwise
it only repeats a field and every row pays the height. Inlines without a
change link use ``CompactTabularInline`` (or set ``show_title = False``), and
this test keeps a new inline from quietly reintroducing the tall row.
"""

from django import forms
from django.contrib import admin
from django.test import TestCase

from booking.admin import BookingInline, ClosureInline
from booking.models import Booking, Closure
from events.admin import EventAttendeesFormInline, EventRegistrationFormInline


class CompactTabularInlineTests(TestCase):
    def test_tabular_inlines_without_a_change_link_drop_the_title_row(self):
        offenders = []
        for model, model_admin in admin.site._registry.items():
            for inline in getattr(model_admin, 'inlines', ()) or ():
                if not isinstance(inline, admin.TabularInline):
                    continue
                if getattr(inline, 'show_change_link', False):
                    continue
                if getattr(inline, 'show_title', True):
                    offenders.append(f'{model._meta.label}.{inline.__name__}')

        self.assertEqual(
            offenders,
            [],
            'These tabular inlines render an extra title row: use CompactTabularInline or set show_title = False.',
        )

    def test_event_inlines_are_compact(self):
        self.assertFalse(EventAttendeesFormInline.show_title)
        self.assertFalse(EventRegistrationFormInline.show_title)


class BookingDescriptionWidgetTests(TestCase):
    """Long descriptions must not be clipped into an 80 pixel input."""

    def test_booking_and_closure_are_stacked_blocks(self):
        for inline_class in (BookingInline, ClosureInline):
            with self.subTest(inline=inline_class.__name__):
                self.assertTrue(issubclass(inline_class, admin.StackedInline))
                self.assertFalse(issubclass(inline_class, admin.TabularInline))

    def test_booking_and_closure_descriptions_render_as_textareas(self):
        for inline_class, model in ((BookingInline, Booking), (ClosureInline, Closure)):
            with self.subTest(inline=inline_class.__name__):
                inline = inline_class(model, admin.site)
                formfield = inline.formfield_for_dbfield(model._meta.get_field('description'), None)

                self.assertIsInstance(formfield.widget, forms.Textarea)
                self.assertEqual(formfield.widget.attrs.get('rows'), 3)
