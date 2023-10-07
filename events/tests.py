from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from events.models import Event
from members.models import Member


class EventTestCase(TestCase):
    def setUp(self):
        self.member = Member.objects.create(username='Test', password='test', is_superuser=True)
        self.event = Event.objects.create(title='Test event',
                                          slug='test',
                                          author_id=self.member.id,
                                          sign_up_deadline=(timezone.now()-timezone.timedelta(-1))
                                          )
        self.assertIsNotNone(self.event)
        self.assertTrue(self.event.published)

    def test_attending_event(self):
        c = Client()
        response = c.post(reverse('events:detail', args=[self.event.slug]),
                          {'user': 'person', 'email': 'person@test.com'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.event.get_registrations().count(), 1)

    def test_duplicate_attendance(self):
        self.assertEqual(self.event.get_registrations().count(), 0)
        c = Client()
        response = c.post(reverse('events:detail', args=[self.event.slug]),
                          {'user': 'person', 'email': 'person@test.com'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.event.get_registrations().count(), 1)
        response = c.post(reverse('events:detail', args=[self.event.slug]),
                          {'user': 'person', 'email': 'person@test.com'})
        # Expect bad request status 400 since duplicate attendance not allowed
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.event.get_registrations().count(), 1)

    def test_unpublished_event(self):
        self.event.unpublish()
        self.assertEqual(self.event.get_registrations().count(), 0)
        c = Client()
        response = c.post(reverse('events:detail', args=[self.event.slug]),
                          {'user': 'person2', 'email': 'person2@test.com'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.event.get_registrations().count(), 1)

    def test_form_validation(self):
        self.assertEqual(self.event.get_registrations().count(), 0)
        c = Client()
        response = c.post(reverse('events:detail', args=[self.event.slug]),
                          {'user': 'person3', 'email': 'no-email-provided'})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.event.get_registrations().count(), 0)

    def test_member_registration(self):
        event = Event.objects.create(title='Test event number 2', slug='test_member_registration',
                                     sign_up_members=timezone.now(),
                                     sign_up_others=timezone.now() + timezone.timedelta(days=7),
                                     author_id=self.member.id)
        self.assertIsNotNone(event)
        c = Client()
        response = c.post(reverse('events:detail', args=[event.slug]), {'user': 'person4', 'email': 'person4@test.com'})
        self.assertEqual(response.status_code, 403)
        self.assertEqual(event.get_registrations().count(), 0)
        # Can not test registration with testuser because auth backend is linked with an external source

    def test_get_event_feed(self):
        c = Client()
        response = c.get(reverse('events:feed'))
        self.assertEqual(response.status_code, 200)

    def test_get_event_detail(self):
        c = Client()
        response = c.get(reverse('events:detail', args=[self.event.slug]))
        self.assertEqual(response.status_code, 200)
        response = c.get(reverse('events:detail', args=['no-such-event']))
        self.assertEqual(response.status_code, 404)

    def test_get_events_index(self):
        c = Client()
        response = c.get(reverse('events:index'))
        self.assertEqual(response.status_code, 200)

    def test_past_deadline(self):
        event = Event.objects.create(title='Test event number 4', slug='test_past_deadline',
                                     sign_up_deadline=timezone.now(),
                                     author_id=self.member.id)
        self.assertIsNotNone(event)
        c = Client(enforce_csrf_checks=False)
        response = c.post(reverse('events:detail', args=[event.slug]), {'user': 'person6', 'email': 'person6@test.com'})
        self.assertEqual(response.status_code, 403)
        self.assertEqual(event.get_registrations().count(), 0)
