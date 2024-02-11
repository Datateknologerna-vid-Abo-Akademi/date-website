import datetime
from django.test import Client, TestCase, RequestFactory
from django.urls import reverse
from django.utils import timezone

from events.forms import PasscodeForm
from events.models import Event
from events.views import EventDetailView
from members.models import Member, ORDINARY_MEMBER, Subscription, SubscriptionPayment


class EventTestCase(TestCase):
    def setUp(self):
        self.member = Member.objects.create(
            username="testuser",
            password="test",
            email="testuser@example.com",
            first_name="Test",
            last_name="User",
            phone="123456789",
            address="123 Test Street",
            zip_code="00000",
            city="Test City",
            country="Finland",
            membership_type=ORDINARY_MEMBER,
            is_superuser=False,
        )

        subscription = Subscription.objects.create(
            name="Basic Subscription",
            does_expire=True,
            renewal_scale="year",
            renewal_period=1,
            price=100.00
        )

        SubscriptionPayment.objects.create(
            member=self.member,
            subscription=subscription,
            date_paid=timezone.now(),
            date_expires=timezone.now() + timezone.timedelta(days=365),
            amount_paid=100.00
        )

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
                          {'user': 'person', 'email': 'person@test.com'}, follow=True)
        self.assertEqual(response.redirect_chain[0][1], 302)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.event.get_registrations().count(), 1)

    def test_duplicate_attendance(self):
        self.assertEqual(self.event.get_registrations().count(), 0)
        c = Client()
        response = c.post(reverse('events:detail', args=[self.event.slug]),
                          {'user': 'person', 'email': 'person@test.com'}, follow=True)
        self.assertEqual(response.redirect_chain[0][1], 302)
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
                          {'user': 'person2', 'email': 'person2@test.com'}, follow=True)
        self.assertEqual(response.redirect_chain[0][1], 302)
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


class EventViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = Member.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='password123'
        )

        self.event = Event.objects.create(
            title="Test Event",
            slug="test-event-view",
            author=self.user,
            sign_up_deadline=timezone.now() + timezone.timedelta(days=1),
            published=True
        )

    def test_event_detail_view_with_and_without_passcode(self):
        self.event.passcode = 'secret'
        self.event.save()

        response = self.client.post(reverse('events:detail', args=[self.event.slug]), {'passcode': 'wrong'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "invalid passcode")

        response_with_passcode = self.client.post(reverse('events:detail', args=[self.event.slug]),
                                                  {'passcode': 'secret'})
        self.assertEqual(response_with_passcode.status_code, 200)
        self.assertNotContains(response_with_passcode, "invalid passcode")

    def test_event_sign_up_deadline_passed(self):
        # Set the signup deadline in the past
        self.event.sign_up_deadline = timezone.now() - timezone.timedelta(days=1)
        self.event.save()

        response = self.client.post(reverse('events:detail', args=[self.event.slug]), {
            'user': 'Late Attendee',
            'email': 'lateattendee@example.com'
        })
        self.assertNotEqual(response.status_code, 200)  # Expecting a redirect or error response

