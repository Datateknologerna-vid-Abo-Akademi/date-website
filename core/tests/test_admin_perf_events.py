"""Focused tests for the event admin performance changes.

These pin the attendee-row writes, the Unfold-only inline pagination and the
indexes the event admin changelists rely on. The full reorder semantics stay in
``events.tests``; this file only covers what the performance pass changed.
"""

import importlib
import uuid
from html.parser import HTMLParser
from unittest import skipIf, skipUnless
from urllib.parse import parse_qs, urlsplit

from django.conf import settings
from django.contrib import admin
from django.db import connection
from django.forms.models import BaseInlineFormSet
from django.test import RequestFactory, SimpleTestCase, TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from core.db_operations import AddIndexConcurrently
from events.admin import EventAttendeesFormInline, EventAttendeesInlineFormSet
from events.models import Event, EventAttendees
from members.models import Member

RUN_ID = uuid.uuid4().hex[:6]
UNFOLD_ENABLED = getattr(settings, 'USE_UNFOLD', False)


def index_names(model):
    return {index.name for index in model._meta.indexes}


class _AttendeePaginationFragment(HTMLParser):
    """Collect only controls and links inside the actual HTMX swap target."""

    def __init__(self, content, selector='#eventattendees_set-data'):
        super().__init__()
        self.target_id = selector.removeprefix('#')
        self.depth = 0
        self.found = False
        self.data = {}
        self.links = []
        self.feed(content)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'div':
            if self.depth:
                self.depth += 1
            elif attrs.get('id') == self.target_id:
                self.depth = 1
                self.found = True
        if not self.depth:
            return
        if tag == 'a' and 'hx-get' in attrs:
            self.links.append(attrs)
        if tag != 'input':
            return
        name = attrs.get('name', '')
        if not name.startswith('eventattendees_set-') or '__prefix__' in name:
            return
        if attrs.get('type') in ('checkbox', 'radio') and 'checked' not in attrs:
            return
        self.data[name] = attrs.get('value', '')

    def handle_endtag(self, tag):
        if tag == 'div' and self.depth:
            self.depth -= 1


class EventIndexTests(SimpleTestCase):
    def test_event_date_start_index_is_declared(self):
        index = next((candidate for candidate in Event._meta.indexes if candidate.name == 'event_date_start_idx'), None)

        self.assertIsNotNone(index)
        self.assertEqual(index.fields, ['event_date_start'])

    def test_attendee_time_registered_index_is_declared(self):
        index = next(
            (
                candidate
                for candidate in EventAttendees._meta.indexes
                if candidate.name == 'attendee_time_registered_idx'
            ),
            None,
        )

        self.assertIsNotNone(index)
        self.assertEqual(index.fields, ['time_registered'])

    def test_existing_event_index_is_kept(self):
        self.assertIn('event_pub_end_idx', index_names(Event))

    def test_migration_creates_the_indexes_concurrently(self):
        migration = importlib.import_module('events.migrations.0027_event_event_date_start_idx_and_more')

        self.assertFalse(migration.Migration.atomic)
        self.assertEqual(len(migration.Migration.operations), 2)
        names = set()
        for operation in migration.Migration.operations:
            self.assertIsInstance(operation, AddIndexConcurrently)
            names.add(operation.index.name)
        self.assertEqual(names, {'event_date_start_idx', 'attendee_time_registered_idx'})


class EventAdminResultCountTests(SimpleTestCase):
    def test_event_admin_skips_the_full_result_count(self):
        self.assertFalse(admin.site._registry[Event].show_full_result_count)

    def test_attendee_admin_skips_the_full_result_count(self):
        self.assertFalse(admin.site._registry[EventAttendees].show_full_result_count)


class AttendeeReorderBulkUpdateTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin_user = Member.objects.create_superuser(
            username=f'pr-{RUN_ID}',
            password='pass',
            email=f'pr-{RUN_ID}@example.com',
        )
        cls.event = Event.objects.create(
            title='Reorder event',
            slug=f'reorder-{RUN_ID}',
            author=cls.admin_user,
        )

    def _create_attendees(self, count):
        EventAttendees.objects.bulk_create(
            [
                EventAttendees(
                    event=self.event,
                    attendee_nr=(index + 1) * 10,
                    user=f'Attendee {index}',
                    email=f'attendee-{index}@example.com',
                    time_registered=timezone.now(),
                    preferences={},
                )
                for index in range(count)
            ]
        )
        return list(EventAttendees.objects.filter(event=self.event).order_by('attendee_nr'))

    def _bound_formset(self, rows, attendee_nrs):
        request = RequestFactory().get('/admin/events/event/change/')
        request.user = self.admin_user
        inline = EventAttendeesFormInline(Event, admin.site)
        formset_class = inline.get_formset(request, obj=self.event)
        data = {
            'eventattendees_set-TOTAL_FORMS': str(len(rows)),
            'eventattendees_set-INITIAL_FORMS': str(len(rows)),
            'eventattendees_set-MIN_NUM_FORMS': '0',
            'eventattendees_set-MAX_NUM_FORMS': '1000',
        }
        for index, (row, attendee_nr) in enumerate(zip(rows, attendee_nrs, strict=True)):
            data[f'eventattendees_set-{index}-id'] = row.pk
            data[f'eventattendees_set-{index}-attendee_nr'] = attendee_nr
            data[f'eventattendees_set-{index}-user'] = row.user
            data[f'eventattendees_set-{index}-email'] = row.email
        return formset_class(
            data=data,
            instance=self.event,
            queryset=EventAttendees.objects.filter(event=self.event),
            prefix='eventattendees_set',
        )

    def test_reorder_writes_the_band_shift_and_restore_in_a_bounded_number_of_updates(self):
        rows = self._create_attendees(40)
        attendee_nrs = [row.attendee_nr for row in rows]
        attendee_nrs[0], attendee_nrs[1] = attendee_nrs[1], attendee_nrs[0]
        formset = self._bound_formset(rows, attendee_nrs)
        self.assertTrue(formset.is_valid(), formset.errors)

        with CaptureQueriesContext(connection) as queries:
            formset.save()

        updates = [query['sql'] for query in queries.captured_queries if query['sql'].lstrip().startswith('UPDATE')]
        # One band shift, one UPDATE for each of the two swapped rows and one
        # restore for the 38 unchanged rows. The old per-row code issued 80
        # UPDATEs for the same save.
        self.assertLessEqual(len(updates), 5)

        numbers_by_pk = dict(EventAttendees.objects.filter(event=self.event).values_list('pk', 'attendee_nr'))
        self.assertEqual(numbers_by_pk[rows[0].pk], rows[1].attendee_nr)
        self.assertEqual(numbers_by_pk[rows[1].pk], rows[0].attendee_nr)
        for row in rows[2:]:
            self.assertEqual(numbers_by_pk[row.pk], row.attendee_nr)


class _AttendeeAdminFixture(TestCase):
    """60 attendees: one full Unfold page plus the off-page remainder."""

    @classmethod
    def setUpTestData(cls):
        cls.admin_user = Member.objects.create_superuser(
            username=f'pp-{RUN_ID}',
            password='pass',
            email=f'pp-{RUN_ID}@example.com',
        )
        cls.event = Event.objects.create(
            title='Paginated event',
            slug=f'paginated-{RUN_ID}',
            author=cls.admin_user,
        )
        EventAttendees.objects.bulk_create(
            [
                EventAttendees(
                    event=cls.event,
                    attendee_nr=(index + 1) * 10,
                    user=f'Attendee {index}',
                    email=f'attendee-{index}@example.com',
                    time_registered=timezone.now(),
                    preferences={},
                )
                for index in range(60)
            ]
        )

    def setUp(self):
        self.client.force_login(self.admin_user)

    @property
    def change_url(self):
        return reverse('admin:events_event_change', args=[self.event.pk])

    def attendee_inline(self, response):
        for inline in response.context['inline_admin_formsets']:
            if inline.formset.prefix == 'eventattendees_set':
                return inline
        self.fail('the attendee inline is missing from the event change page')


@skipUnless(UNFOLD_ENABLED, 'Unfold is the only admin that paginates the attendee inline')
class AttendeeInlinePaginationTests(_AttendeeAdminFixture):
    def _paginated_formset(self, page=1):
        request = RequestFactory().get(self.change_url, {'eventattendees_set-page': str(page)})
        request.user = self.admin_user
        inline = EventAttendeesFormInline(Event, admin.site)
        formset_class = inline.get_formset(request, obj=self.event)
        return formset_class(
            request=request,
            per_page=inline.per_page,
            instance=self.event,
            queryset=EventAttendees.objects.filter(event=self.event),
            prefix='eventattendees_set',
        )

    def _fragment(self, response, selector='#eventattendees_set-data'):
        fragment = _AttendeePaginationFragment(response.content.decode(), selector)
        self.assertTrue(fragment.found, 'the HTMX target must be a div containing the management form and rows')
        return fragment

    def _follow_page(self, fragment, page):
        link = next(
            link
            for link in fragment.links
            if parse_qs(urlsplit(link['hx-get']).query).get('eventattendees_set-page') == [str(page)]
        )
        self.assertEqual(link['hx-select'], '#eventattendees_set-data')
        self.assertEqual(link['hx-target'], link['hx-select'])
        response = self.client.get(self.change_url + link['hx-get'], headers={'HX-Request': 'true'})
        self.assertEqual(response.status_code, 200)
        return self._fragment(response, link['hx-select'])

    def _bound_fragment(self, fragment):
        request = RequestFactory().post(self.change_url, fragment.data)
        request.user = self.admin_user
        inline = EventAttendeesFormInline(Event, admin.site)
        formset_class = inline.get_formset(request, obj=self.event)
        return formset_class(
            data=fragment.data,
            request=request,
            per_page=inline.per_page,
            instance=self.event,
            queryset=EventAttendees.objects.filter(event=self.event),
            prefix='eventattendees_set',
        )

    def test_htmx_last_page_and_return_replace_management_counts_and_save(self):
        fragment = self._fragment(self.client.get(self.change_url))
        self.assertEqual(fragment.data['eventattendees_set-TOTAL_FORMS'], '50')
        for page, count in ((2, 10), (1, 50)):
            with self.subTest(page=page):
                fragment = self._follow_page(fragment, page)
                self.assertEqual(fragment.data['eventattendees_set-TOTAL_FORMS'], str(count))
                self.assertEqual(fragment.data['eventattendees_set-INITIAL_FORMS'], str(count))
                self.assertEqual(fragment.data['eventattendees_set-page'], str(page))
                self.assertEqual(sum(name.endswith('-id') for name in fragment.data), count)
                pk = fragment.data['eventattendees_set-0-id']
                fragment.data['eventattendees_set-0-user'] = f'Edited page {page}'
                formset = self._bound_fragment(fragment)
                self.assertTrue(formset.is_valid(), formset.errors)
                formset.save()
                self.assertEqual(EventAttendees.objects.get(pk=pk).user, f'Edited page {page}')
        self.assertEqual(EventAttendees.objects.filter(event=self.event).count(), 60)

    def test_native_unfold_ranks_only_permute_the_current_pages_gapped_slots(self):
        EventAttendees.objects.filter(event=self.event).delete()
        numbers = [0, 2, 3, *(103 + index * 17 for index in range(117))]
        EventAttendees.objects.bulk_create(
            [
                EventAttendees(
                    event=self.event,
                    attendee_nr=nr,
                    user=f'Gapped attendee {index}',
                    email=f'gapped-{index}@example.com',
                    time_registered=timezone.now(),
                    preferences={},
                )
                for index, nr in enumerate(numbers)
            ]
        )
        for page in (1, 2, 3):
            with self.subTest(page=page):
                rows = list(EventAttendees.objects.filter(event=self.event).order_by('attendee_nr'))
                before = {row.pk: row.attendee_nr for row in rows}
                page_rows = rows[(page - 1) * 50 : page * 50]
                slots = [row.attendee_nr for row in page_rows]
                response = self.client.get(self.change_url, {'eventattendees_set-page': str(page)})
                fragment = self._fragment(response)
                # Native Unfold sortRecords uses zero-based ranks after dragging
                # the last visible row first, including on later pages.
                for index in range(len(page_rows)):
                    fragment.data[f'eventattendees_set-{index}-attendee_nr'] = str((index + 1) % len(page_rows))
                formset = self._bound_fragment(fragment)
                self.assertTrue(formset.is_valid(), formset.errors)
                if page == 1:
                    # Original nr=2 and submitted rank=2 compare equal before
                    # normalization, but the mapped slot is 3 and must save.
                    self.assertIn('attendee_nr', formset.initial_forms[1].changed_data)
                formset.save()
                expected = before.copy()
                for index, row in enumerate(page_rows):
                    expected[row.pk] = slots[(index + 1) % len(page_rows)]
                after = dict(EventAttendees.objects.filter(event=self.event).values_list('pk', 'attendee_nr'))
                self.assertEqual(after, expected)

    def test_edit_without_drag_preserves_the_current_pages_number_slots(self):
        rows = list(EventAttendees.objects.filter(event=self.event).order_by('attendee_nr')[50:])
        for index, row in enumerate(rows):
            row.attendee_nr = 1003 + index * 17
        EventAttendees.objects.bulk_update(rows, ['attendee_nr'])
        fragment = self._fragment(self.client.get(self.change_url, {'eventattendees_set-page': '2'}))
        before = dict(EventAttendees.objects.filter(event=self.event).values_list('pk', 'attendee_nr'))
        fragment.data['eventattendees_set-0-user'] = 'Edited without dragging'
        formset = self._bound_fragment(fragment)
        self.assertTrue(formset.is_valid(), formset.errors)
        formset.save()
        self.assertEqual(dict(EventAttendees.objects.filter(event=self.event).values_list('pk', 'attendee_nr')), before)

    def test_native_reorder_with_a_new_row_is_rejected_without_writing(self):
        fragment = self._fragment(self.client.get(self.change_url, {'eventattendees_set-page': '2'}))
        before = dict(EventAttendees.objects.filter(event=self.event).values_list('pk', 'attendee_nr'))
        fragment.data['eventattendees_set-TOTAL_FORMS'] = '11'
        for index in range(10):
            fragment.data[f'eventattendees_set-{index}-attendee_nr'] = str(index + 1)
        fragment.data.update(
            {
                'eventattendees_set-10-attendee_nr': '0',
                'eventattendees_set-10-user': 'New attendee dragged first',
                'eventattendees_set-10-email': 'new-dragged@example.com',
            }
        )
        formset = self._bound_fragment(fragment)
        self.assertFalse(formset.is_valid())
        self.assertEqual(formset.non_form_errors(), ['Spara nya deltagare innan du ändrar ordningen.'])
        self.assertEqual(dict(EventAttendees.objects.filter(event=self.event).values_list('pk', 'attendee_nr')), before)

    def test_adding_without_drag_does_not_reject_or_renumber_existing_rows(self):
        fragment = self._fragment(self.client.get(self.change_url, {'eventattendees_set-page': '2'}))
        before = dict(EventAttendees.objects.filter(event=self.event).values_list('pk', 'attendee_nr'))
        fragment.data['eventattendees_set-TOTAL_FORMS'] = '11'
        fragment.data.update(
            {
                'eventattendees_set-10-attendee_nr': '610',
                'eventattendees_set-10-user': 'New attendee',
                'eventattendees_set-10-email': 'new@example.com',
            }
        )
        formset = self._bound_fragment(fragment)
        self.assertTrue(formset.is_valid(), formset.errors)
        formset.save()
        self.assertEqual(dict(EventAttendees.objects.filter(pk__in=before).values_list('pk', 'attendee_nr')), before)
        self.assertTrue(EventAttendees.objects.filter(event=self.event, email='new@example.com').exists())

    def test_native_reorder_with_a_deleted_row_leaves_off_page_numbers_unchanged(self):
        fragment = self._fragment(self.client.get(self.change_url, {'eventattendees_set-page': '2'}))
        rows = list(EventAttendees.objects.filter(event=self.event).order_by('attendee_nr'))
        expected = {row.pk: row.attendee_nr for row in rows[:50]}
        page_rows = rows[50:]
        slots = [row.attendee_nr for row in page_rows]
        for index, row in enumerate(page_rows):
            rank = (index + 1) % len(page_rows)
            fragment.data[f'eventattendees_set-{index}-attendee_nr'] = str(rank)
            if index != 3:
                expected[row.pk] = slots[rank]
        fragment.data['eventattendees_set-3-DELETE'] = 'on'
        formset = self._bound_fragment(fragment)
        self.assertTrue(formset.is_valid(), formset.errors)
        formset.save()
        self.assertEqual(
            dict(EventAttendees.objects.filter(event=self.event).values_list('pk', 'attendee_nr')), expected
        )

    def test_inline_paginates_fifty_attendees_per_page(self):
        self.assertEqual(EventAttendeesFormInline.per_page, 50)

        formset = self._paginated_formset()

        self.assertEqual(formset.paginator.count, 60)
        self.assertEqual(len(formset.initial_forms), 50)
        self.assertEqual(formset.page.number, 1)

    def test_add_page_has_no_attendee_page_to_load(self):
        # With no saved parent the inline queryset is none(), and the pagination
        # mixin must still build a page instead of raising on an empty paginator.
        response = self.client.get(reverse('admin:events_event_add'))

        self.assertEqual(response.status_code, 200)
        inline = self.attendee_inline(response)
        self.assertEqual(len(inline.formset.initial_forms), 0)

    def test_second_page_holds_the_remaining_attendees(self):
        formset = self._paginated_formset(page=2)

        self.assertEqual(len(formset.initial_forms), 10)
        self.assertEqual(formset.page.number, 2)
        self.assertEqual(
            [form.instance.attendee_nr for form in formset.initial_forms],
            [(index + 1) * 10 for index in range(50, 60)],
        )

    def test_change_page_renders_only_the_first_page(self):
        response = self.client.get(self.change_url)

        self.assertEqual(response.status_code, 200)
        inline = self.attendee_inline(response)
        self.assertEqual(len(inline.formset.initial_forms), 50)
        self.assertEqual(inline.formset.page.paginator.count, 60)
        self.assertContains(response, 'eventattendees_set-page')

    def test_second_page_of_the_change_form_renders_the_rest(self):
        response = self.client.get(self.change_url, {'eventattendees_set-page': '2'})

        self.assertEqual(response.status_code, 200)
        inline = self.attendee_inline(response)
        self.assertEqual(len(inline.formset.initial_forms), 10)
        self.assertEqual(inline.formset.page.number, 2)
        self.assertEqual(inline.formset.initial_forms[0].instance.attendee_nr, 510)

    def test_saving_one_page_keeps_off_page_attendees(self):
        request = RequestFactory().get(self.change_url)
        request.user = self.admin_user
        inline = EventAttendeesFormInline(Event, admin.site)
        formset_class = inline.get_formset(request, obj=self.event)
        rows = list(EventAttendees.objects.filter(event=self.event).order_by('attendee_nr')[:50])
        attendee_nrs = [row.attendee_nr for row in rows]
        # A page-local reorder drag, exactly what admin_ordering submits.
        attendee_nrs[0], attendee_nrs[1] = attendee_nrs[1], attendee_nrs[0]
        data = {
            'eventattendees_set-TOTAL_FORMS': str(len(rows)),
            'eventattendees_set-INITIAL_FORMS': str(len(rows)),
            'eventattendees_set-MIN_NUM_FORMS': '0',
            'eventattendees_set-MAX_NUM_FORMS': '1000',
            'eventattendees_set-page': '1',
        }
        for index, (row, attendee_nr) in enumerate(zip(rows, attendee_nrs, strict=True)):
            data[f'eventattendees_set-{index}-id'] = row.pk
            data[f'eventattendees_set-{index}-attendee_nr'] = attendee_nr
            data[f'eventattendees_set-{index}-user'] = row.user
            data[f'eventattendees_set-{index}-email'] = row.email
        formset = formset_class(
            data=data,
            request=request,
            per_page=inline.per_page,
            instance=self.event,
            queryset=EventAttendees.objects.filter(event=self.event),
            prefix='eventattendees_set',
        )
        self.assertTrue(formset.is_valid(), formset.errors)

        formset.save()

        self.assertEqual(EventAttendees.objects.filter(event=self.event).count(), 60)
        off_page = list(EventAttendees.objects.filter(event=self.event).order_by('attendee_nr')[50:])
        self.assertEqual([row.attendee_nr for row in off_page], [(index + 1) * 10 for index in range(50, 60)])
        numbers_by_pk = dict(EventAttendees.objects.filter(event=self.event).values_list('pk', 'attendee_nr'))
        self.assertEqual(numbers_by_pk[rows[0].pk], rows[1].attendee_nr)
        self.assertEqual(numbers_by_pk[rows[1].pk], rows[0].attendee_nr)


@skipIf(UNFOLD_ENABLED, 'the classic admin keeps the unpaginated attendee inline')
class AttendeeInlineClassicAdminTests(_AttendeeAdminFixture):
    def test_formset_stays_a_plain_inline_formset(self):
        self.assertEqual(EventAttendeesInlineFormSet.__mro__[1], BaseInlineFormSet)

    def test_change_page_still_renders_every_attendee(self):
        response = self.client.get(self.change_url)

        self.assertEqual(response.status_code, 200)
        inline = self.attendee_inline(response)
        self.assertEqual(len(inline.formset.initial_forms), 60)
