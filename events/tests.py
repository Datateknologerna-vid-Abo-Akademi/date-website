import logging
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.conf import settings
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from events.models import Event, EventAttendees, EventRegistrationForm
from events.websocket_utils import ws_data, ws_send
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


class EventRegistrationWindowTests(TestCase):
    def setUp(self):
        self.membership_type = MembershipType.objects.get(pk=ORDINARY_MEMBER)
        self.author = Member.objects.create_user(
            username="window-tester",
            password="pwd",
            membership_type=self.membership_type,
        )

    def _create_event(self):
        return Event.objects.create(
            title="Window Event",
            slug=f"window-event-{Event.objects.count()}",
            author=self.author,
            sign_up_members=None,
            sign_up_others=None,
            sign_up_deadline=None,
        )

    def test_member_registration_window_requires_start_time(self):
        event = self._create_event()
        self.assertFalse(event.registration_is_open_members())

        event.sign_up_members = timezone.now() - timezone.timedelta(minutes=1)
        event.save()
        self.assertTrue(event.registration_is_open_members())

        event.sign_up_deadline = timezone.now() - timezone.timedelta(minutes=1)
        event.save()
        self.assertTrue(event.registration_past_due())
        self.assertFalse(event.registration_is_open_members())

    def test_open_for_others_respects_deadline(self):
        event = self._create_event()
        event.sign_up_others = timezone.now() - timezone.timedelta(minutes=5)
        event.sign_up_deadline = timezone.now() + timezone.timedelta(days=1)
        event.save()
        self.assertTrue(event.registration_is_open_others())

        event.sign_up_deadline = timezone.now() - timezone.timedelta(seconds=1)
        event.save()
        self.assertFalse(event.registration_is_open_others())


class EventCapacityTests(TestCase):
    def setUp(self):
        self.membership_type = MembershipType.objects.get(pk=ORDINARY_MEMBER)
        self.author = Member.objects.create_user(
            username="capacity-author",
            password="pwd",
            membership_type=self.membership_type,
        )

    def test_child_event_uses_parent_attendance_for_capacity(self):
        parent = Event.objects.create(
            title="Parent Event",
            slug="parent-event",
            author=self.author,
            sign_up_max_participants=0,
        )
        child = Event.objects.create(
            title="Child Event",
            slug="child-event",
            author=self.author,
            parent=parent,
            sign_up_max_participants=1,
        )
        EventAttendees.objects.create(
            event=parent,
            original_event=child,
            user="Registered",
            email="child@example.com",
            time_registered=timezone.now(),
            preferences={},
        )

        self.assertTrue(child.event_is_full())
        self.assertFalse(parent.event_is_full())


@override_settings(CONTENT_VARIABLES={**settings.CONTENT_VARIABLES, "INTERNATIONAL_EVENT_SLUGS": ["intl-slug"]})
class EventFormBuilderTests(TestCase):
    def setUp(self):
        self.membership_type = MembershipType.objects.get(pk=ORDINARY_MEMBER)
        self.author = Member.objects.create_user(
            username="form-author",
            password="pwd",
            membership_type=self.membership_type,
        )
        self.event = Event.objects.create(
            title="International Event",
            slug="intl-slug",
            author=self.author,
            sign_up_avec=True,
        )
        EventRegistrationForm.objects.create(
            event=self.event,
            name="meal",
            type="select",
            choice_list="fish,veg",
            required=True,
            choice_number=10,
        )
        EventRegistrationForm.objects.create(
            event=self.event,
            name="notes",
            type="text",
            required=False,
            choice_number=20,
        )
        EventRegistrationForm.objects.create(
            event=self.event,
            name="hidden",
            type="checkbox",
            required=False,
            hide_for_avec=True,
            choice_number=30,
        )

    def test_dynamic_form_contains_expected_fields_and_labels(self):
        form_class = self.event.make_registration_form()
        form = form_class()

        expected_order = [
            "user",
            "email",
            "anonymous",
            "meal",
            "notes",
            "hidden",
            "avec",
            "avec_user",
            "avec_email",
            "avec_anonymous",
            "avec_meal",
            "avec_notes",
        ]
        self.assertEqual(list(form.base_fields.keys()), expected_order)
        self.assertEqual(form.base_fields["user"].label, "Nimi/Namn/Name")
        self.assertEqual(form.base_fields["anonymous"].label, "Anonyymi/Anonym/Anonymous")
        self.assertNotIn("avec_hidden", form.base_fields)


class EventNumberingTests(TestCase):
    def setUp(self):
        self.membership_type = MembershipType.objects.get(pk=ORDINARY_MEMBER)
        self.author = Member.objects.create_user(
            username="number-author",
            password="pwd",
            membership_type=self.membership_type,
        )
        self.event = Event.objects.create(
            title="Numbered Event",
            slug="numbered-event",
            author=self.author,
        )

    def test_choice_numbers_increment_by_ten(self):
        first = EventRegistrationForm.objects.create(event=self.event, name="first")
        second = EventRegistrationForm.objects.create(event=self.event, name="second")
        self.assertEqual(first.choice_number, 10)
        self.assertEqual(second.choice_number, 20)

        first.delete()
        third = EventRegistrationForm.objects.create(event=self.event, name="third")
        self.assertEqual(third.choice_number, 30)

    def test_attendee_numbers_and_preferences(self):
        attendee1 = EventAttendees.objects.create(
            event=self.event,
            user="First",
            email="first@example.com",
            preferences=[],
            time_registered=None,
        )
        attendee2 = EventAttendees.objects.create(
            event=self.event,
            user="Second",
            email="second@example.com",
            preferences=[],
            time_registered=None,
        )
        self.assertEqual(attendee1.attendee_nr, 10)
        self.assertEqual(attendee2.attendee_nr, 20)

        attendee1.delete()
        attendee3 = EventAttendees.objects.create(
            event=self.event,
            user="Third",
            email="third@example.com",
            preferences=[],
            time_registered=None,
        )
        self.assertEqual(attendee3.attendee_nr, 30)
        self.assertEqual(attendee3.preferences, {})
        self.assertIsNotNone(attendee3.time_registered)


class EventTemplateSelectionTests(TestCase):
    def setUp(self):
        self.membership_type = MembershipType.objects.get(pk=ORDINARY_MEMBER)
        self.author = Member.objects.create_user(
            username="template-author",
            password="pwd",
            membership_type=self.membership_type,
        )

    def test_title_based_template_selected(self):
        event = Event.objects.create(
            title="Årsfest",
            slug="arsfest",
            author=self.author,
        )
        response = self.client.get(reverse("events:detail", args=[event.slug]))
        self.assertTemplateUsed(response, "events/arsfest.html")

    def test_slug_based_template_selected(self):
        event = Event.objects.create(
            title="Generic",
            slug="baal",
            author=self.author,
        )
        response = self.client.get(reverse("events:detail", args=[event.slug]))
        self.assertTemplateUsed(response, "events/baal_detail.html")

    def test_passcode_template_used_when_locked(self):
        event = Event.objects.create(
            title="Secret Event",
            slug="secret-event",
            author=self.author,
            passcode="secret",
        )
        response = self.client.get(reverse("events:detail", args=[event.slug]))
        self.assertTemplateUsed(response, "events/event_passcode.html")


class EventWebsocketUtilsTests(TestCase):
    class PublicInfo:
        def __init__(self, name):
            self.name = name

        def __str__(self):
            return self.name

    def test_ws_send_emits_messages_for_avec_signups(self):
        form = SimpleNamespace(cleaned_data={
            "user": "Primary",
            "email": "primary@example.com",
            "anonymous": False,
            "avec": True,
            "avec_user": "Guest",
            "avec_email": "guest@example.com",
            "meal": "veg",
        })
        public_info = [self.PublicInfo("meal")]
        group_send = MagicMock()

        with patch("events.websocket_utils.get_channel_layer", return_value=SimpleNamespace(group_send=group_send)), \
                patch("events.websocket_utils.async_to_sync", side_effect=lambda func: func):
            ws_send("event-slug", form, public_info)

        self.assertEqual(group_send.call_count, 2)
        first_payload = group_send.call_args_list[0].args[1]
        second_payload = group_send.call_args_list[1].args[1]
        self.assertEqual(first_payload["data"]["fields"][0], ("user", "Primary"))
        self.assertEqual(second_payload["data"]["fields"][0], ("user", "Guest"))

    def test_ws_data_masks_anonymous_name_and_filters_public_info(self):
        form = SimpleNamespace(cleaned_data={
            "user": "Hidden",
            "anonymous": True,
            "allergies": "nuts",
        })
        public_info = [self.PublicInfo("allergies")]

        payload = ws_data(form, public_info)

        self.assertEqual(payload["data"]["fields"][0], ("user", "Anonymt"))
        self.assertEqual(payload["data"]["fields"][1], ("allergies", "nuts"))
