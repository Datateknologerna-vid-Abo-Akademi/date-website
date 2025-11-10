import logging
from unittest.mock import patch

from django.core.cache import cache
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from core.cache_keys import EVENTS_INDEX_CACHE_KEY
from events.models import Event, EventAttendees, EventRegistrationForm
from members.models import Member, ORDINARY_MEMBER, Subscription, SubscriptionPayment, MembershipType

logger = logging.getLogger('date')


class EventTestCase(TestCase):
    def setUp(self):
        self.member = Member.objects.create_user(
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
            membership_type=MembershipType.objects.get(pk=ORDINARY_MEMBER),
            is_superuser=False,
            is_active=True,
        )

        subscription = Subscription.objects.create(
            name="Basic Subscription",
            does_expire=True,
            renewal_scale="year",
            renewal_period=1,
            price=100.00
        )

        self.subpay = SubscriptionPayment.objects.create(
            member=self.member,
            subscription=subscription,
            date_paid=timezone.now() - timezone.timedelta(days=1),
            date_expires=timezone.now() + timezone.timedelta(days=365),
            amount_paid=100.00
        )

        self.event = Event.objects.create(title='Test event',
                                          slug='test',
                                          author_id=self.member.id,
                                          sign_up_deadline=(timezone.now() + timezone.timedelta(days=7))
                                          )
        self.content = {'user': 'person', 'email': 'person@test.com'}
        self.assertIsNotNone(self.event)
        self.assertTrue(self.event.published)

    def test_attending_event(self):
        c = Client()
        response = c.post(reverse('events:detail', args=[self.event.slug]), self.content, follow=True)
        self.assertEqual(response.redirect_chain[0][1], 302)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.event.get_registrations().count(), 1)

    def test_duplicate_attendance(self):
        self.assertEqual(self.event.get_registrations().count(), 0)
        c = Client()
        response = c.post(reverse('events:detail', args=[self.event.slug]), self.content, follow=True)
        self.assertEqual(response.redirect_chain[0][1], 302)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.event.get_registrations().count(), 1)
        response = c.post(reverse('events:detail', args=[self.event.slug]), self.content)
        # Expect bad request status 400 since duplicate attendance not allowed
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.event.get_registrations().count(), 1)

    def test_unpublished_event(self):
        self.event.unpublish()
        self.assertEqual(self.event.get_registrations().count(), 0)
        c = Client()
        response = c.post(reverse('events:detail', args=[self.event.slug]),
                          {'user': 'person', 'email': 'person@test.com'}, follow=True)
        self.assertEqual(response.redirect_chain[0][1], 302)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.event.get_registrations().count(), 1)

    def test_form_validation(self):
        self.assertEqual(self.event.get_registrations().count(), 0)
        c = Client()
        self.content['email'] = 'no-email-provided'
        response = c.post(reverse('events:detail', args=[self.event.slug]), self.content)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.event.get_registrations().count(), 0)

    def test_member_registration(self):
        self.event.sign_up_members = timezone.now()
        self.event.sign_up_others = timezone.now() + timezone.timedelta(days=5)
        self.event.save()
        self.assertIsNotNone(self.event)
        c = Client()
        response = c.post(reverse('events:detail', args=[self.event.slug]), self.content)
        self.assertEqual(response.status_code, 403)
        self.assertEqual(self.event.get_registrations().count(), 0)

    def test_member_registration_with_subscription(self):
        self.event.sign_up_members = timezone.now() - timezone.timedelta(days=1)
        self.event.sign_up_others = timezone.now() + timezone.timedelta(days=1)
        self.event.save()
        c = Client()
        c.login(username=self.member.username, password='test')
        response = c.post(reverse('events:detail', args=[self.event.slug]), self.content, follow=True)
        self.assertIsNotNone(self.event.sign_up_members)
        self.assertEqual(response.status_code, 200)

        self.event.sign_up_members = timezone.now() + timezone.timedelta(days=1)
        self.event.save()
        self.content['email'] = 'person2@test.com'
        response = c.post(reverse('events:detail', args=[self.event.slug]), self.content, follow=True)
        self.assertEqual(response.status_code, 403)

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
        self.event.sign_up_deadline = timezone.now()
        self.event.save()
        self.assertIsNotNone(self.event)
        c = Client()
        response = c.post(reverse('events:detail', args=[self.event.slug]), self.content)
        self.assertEqual(response.status_code, 403)
        self.assertEqual(self.event.get_registrations().count(), 0)

    def test_event_detail_view_with_and_without_passcode(self):
        self.event.passcode = 'secret'
        self.event.save()
        c = Client()
        wrong, right = {'passcode': 'wrong'}, {'passcode': 'secret'}
        incorrect = c.post(reverse('events:detail', args=[self.event.slug]), wrong)
        self.assertEqual(incorrect.status_code, 401)
        correct = c.post(reverse('events:detail', args=[self.event.slug]), right)
        self.assertEqual(correct.status_code, 200)
        self.assertNotContains(correct, "invalid passcode")

    def test_sign_up_members_before_sign_up_open(self):
        self.event.sign_up_members = timezone.now() + timezone.timedelta(days=1)
        self.event.sign_up_others = timezone.now() + timezone.timedelta(days=1)
        self.event.save()
        c = Client()
        c.login(username=self.member.username, password='test')
        response = c.post(reverse('events:detail', args=[self.event.slug]), self.content)
        self.assertEqual(response.status_code, 403)

    def test_sign_up_members_without_subscription(self):
        self.event.sign_up_members = timezone.now() - timezone.timedelta(days=1)
        self.event.sign_up_others = timezone.now() + timezone.timedelta(days=1)
        self.event.save()
        self.subpay.delete()
        c = Client()
        c.login(username=self.member.username, password='test')
        response = c.post(reverse('events:detail', args=[self.event.slug]), self.content, follow=True)
        self.assertEqual(response.status_code, 403)

    def test_avec_data_posting(self):
        self.event.sign_up_avec = True
        self.event.save()
        c = Client()
        avec_data = {'avec': 'on', 'avec_user': 'Avec Person', 'avec_email': 'avec@test.com'}
        self.content.update(avec_data)
        response = c.post(reverse('events:detail', args=[self.event.slug]), self.content, follow=True)
        self.assertEqual(response.status_code, 200)
        person_registration = self.event.get_registrations().first()
        self.assertEqual(person_registration.user, 'person')
        self.assertEqual(person_registration.email, 'person@test.com')
        avec_registration = self.event.get_registrations().last()
        self.assertIsNotNone(avec_registration)
        self.assertEqual(avec_registration.user, 'Avec Person')
        self.assertEqual(avec_registration.email, 'avec@test.com')

    def test_redirect_link(self):
        self.event.redirect_link = 'https://www.google.com'
        self.event.save()
        c = Client()
        response = c.get(reverse('events:detail', args=[self.event.slug]))
        logger.debug(response.status_code)
        logger.debug(response.content)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers['Location'], 'https://www.google.com')

    def test_events_index_populates_cache(self):
        cache.delete(EVENTS_INDEX_CACHE_KEY)
        response = self.client.get(reverse('events:index'))
        self.assertEqual(response.status_code, 200)
        cached = cache.get(EVENTS_INDEX_CACHE_KEY)
        self.assertIsNotNone(cached)
        self.assertEqual(cached.status_code, response.status_code)

    def test_attendee_numbering_increments(self):
        first = EventAttendees.objects.create(
            event=self.event,
            user='First',
            email='first@example.com',
            time_registered=timezone.now()
        )
        second = EventAttendees.objects.create(
            event=self.event,
            user='Second',
            email='second@example.com',
            time_registered=timezone.now()
        )
        first.refresh_from_db()
        second.refresh_from_db()
        self.assertEqual(first.attendee_nr, 10)
        self.assertEqual(second.attendee_nr, 20)

    def test_attendee_numbering_after_gap(self):
        attendees = []
        for i in range(3):
            attendee = EventAttendees.objects.create(
                event=self.event,
                user=f'User {i}',
                email=f'user{i}@example.com',
                time_registered=timezone.now()
            )
            attendee.refresh_from_db()
            attendees.append(attendee)
        attendees[1].delete()
        fourth = EventAttendees.objects.create(
            event=self.event,
            user='Fourth',
            email='fourth@example.com',
            time_registered=timezone.now()
        )
        fourth.refresh_from_db()
        self.assertEqual(fourth.attendee_nr, attendees[2].attendee_nr + 10)

    def test_anonymous_attendance(self):
        c = Client()
        self.content['anonymous'] = 'on'
        c.post(reverse('events:detail', args=[self.event.slug]), self.content)
        details = c.get(reverse('events:detail', args=[self.event.slug]))
        self.assertEqual(self.event.get_registrations().last().anonymous, True)
        self.assertContains(details, '<i>Anonymt</i>', count=1)

    def test_custom_fields(self):
        EventRegistrationForm(event=self.event, choice_number=1, name='field1',
                              type='text', required=False, public_info=True).save()
        EventRegistrationForm(event=self.event, choice_number=2, name='field2',
                              type='select', required=False, public_info=True,
                              choice_list='choice 1,choice 2,choice 3').save()
        EventRegistrationForm(event=self.event, choice_number=3, name='field3',
                              type='checkbox', required=False, public_info=True).save()

        c = Client()
        response = c.get(reverse('events:detail', args=[self.event.slug]))
        self.assertNotContains(response, 'Test value')
        self.assertContains(response, 'choice 2', count=2)
        self.assertNotContains(response, '<td>True</td>')

        choices = {'field1': 'Test value', 'field2': 'choice 2', 'field3': 'on'}
        self.content.update(choices)
        c.post(reverse('events:detail', args=[self.event.slug]), self.content)
        response = c.get(reverse('events:detail', args=[self.event.slug]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Test value', count=1)
        self.assertContains(response, 'choice 2', count=3)
        self.assertContains(response, '<td>True</td>', count=1)

    def test_max_participants(self):
        self.event.sign_up_max_participants = 1
        self.event.save()
        c = Client()

        c.post(reverse('events:detail', args=[self.event.slug]), self.content)
        self.content['email'] = 'person2@test.com'
        response = c.post(reverse('events:detail', args=[self.event.slug]), self.content, follow=True)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.event.get_registrations().count(), 2)

    @patch('events.views.validate_captcha')
    @override_settings(CAPTCHA_SITE_KEY='test', TURNSTILE_SECRET_KEY='test')
    def test_captcha(self, mock_validate_captcha):
        mock_validate_captcha.return_value = False
        self.event.captcha = True
        self.event.save()

        c = Client()
        response = c.post(reverse('events:detail', args=[self.event.slug]), self.content)

        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.event.get_registrations().count(), 0)

        mock_validate_captcha.return_value = True
        content = {'user': 'person', 'email': 'person@test.com', 'cf-turnstile-response': 'test'}
        response = c.post(reverse('events:detail', args=[self.event.slug]), content, follow=True)
        mock_validate_captcha.assert_called()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.event.get_registrations().count(), 1)
