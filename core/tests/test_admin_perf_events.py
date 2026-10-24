"""Focused tests for the event admin performance changes.

These pin the attendee-row writes, the Unfold-only inline pagination and the
indexes the event admin changelists rely on. The full reorder semantics stay in
``events.tests``; this file only covers what the performance pass changed.
"""

import importlib
import uuid
from unittest import skipIf, skipUnless

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
