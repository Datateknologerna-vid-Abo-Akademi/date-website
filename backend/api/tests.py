import datetime
from unittest.mock import patch

from django.contrib.auth.tokens import default_token_generator
from django.conf import settings
from django.test import TestCase, override_settings
from django.utils import timezone
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from alumni.models import AlumniUpdateToken
from archive.models import Collection
from billing.models import EventBillingConfiguration, EventInvoice
from ctf.models import Ctf, Flag, Guess
from events.models import Event, EventAttendees, EventRegistrationForm
from members.models import MembershipType, Member
from members.tokens import account_activation_token
from social.models import Harassment, HarassmentEmailRecipient


class ApiSmokeTests(TestCase):
    def setUp(self):
        self.membership_type = MembershipType.objects.create(name="Ordinarie")
        self.member = Member.objects.create(
            username="tester",
            email="tester@example.com",
            membership_type=self.membership_type,
            first_name="Test",
            last_name="User",
        )
        self.member.set_password("password123")
        self.member.save()

    def test_meta_site_endpoint(self):
        response = self.client.get("/api/v1/meta/site")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("data", payload)
        self.assertIn("enabled_modules", payload["data"])
        self.assertIn("module_capabilities", payload["data"])
        self.assertIn("events", payload["data"]["module_capabilities"])
        self.assertIn("enabled", payload["data"]["module_capabilities"]["events"])
        self.assertIn("label", payload["data"]["module_capabilities"]["events"])
        self.assertIn("nav_route", payload["data"]["module_capabilities"]["events"])
        self.assertIn("features", payload["data"]["module_capabilities"]["events"])
        self.assertIn("default_landing_path", payload["data"])

    def test_home_endpoint(self):
        response = self.client.get("/api/v1/home")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("data", payload)
        self.assertIn("events", payload["data"])
        self.assertIn("news", payload["data"])

    def test_member_profile_requires_auth(self):
        response = self.client.get("/api/v1/members/me")
        self.assertEqual(response.status_code, 403)

    def test_session_endpoint_sets_csrf_cookie_when_anonymous(self):
        response = self.client.get("/api/v1/auth/session")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"]["is_authenticated"], False)
        self.assertIn(settings.CSRF_COOKIE_NAME, response.cookies)

    def test_session_endpoint_returns_identity_when_authenticated(self):
        self.client.login(username="tester", password="password123")
        response = self.client.get("/api/v1/auth/session")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"]["is_authenticated"], True)
        self.assertEqual(response.json()["data"]["username"], "tester")

    def test_member_profile_when_logged_in(self):
        self.client.login(username="tester", password="password123")
        response = self.client.get("/api/v1/members/me")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"]["username"], "tester")

    def test_polls_list_endpoint(self):
        response = self.client.get("/api/v1/polls")
        self.assertEqual(response.status_code, 200)
        self.assertIn("data", response.json())

    def test_archive_requires_auth(self):
        response = self.client.get("/api/v1/archive/pictures/years")
        self.assertEqual(response.status_code, 401)

    def test_archive_years_when_logged_in(self):
        self.client.login(username="tester", password="password123")
        response = self.client.get("/api/v1/archive/pictures/years")
        self.assertEqual(response.status_code, 200)
        self.assertIn("data", response.json())

    def test_publications_list_endpoint(self):
        response = self.client.get("/api/v1/publications")
        self.assertEqual(response.status_code, 200)
        self.assertIn("data", response.json())

    @patch("api.views.validate_captcha", return_value=True)
    @patch("api.views.send_email_task.delay")
    def test_social_harassment_report_submit(self, mocked_send_email, _mocked_captcha):
        HarassmentEmailRecipient.objects.create(recipient_email="board@example.com")
        response = self.client.post(
            "/api/v1/social/harassment",
            {
                "email": "anonymous@example.com",
                "message": "Test report",
                "consent": True,
            },
        )
        self.assertEqual(response.status_code, 201)
        self.assertTrue(response.json()["data"]["submitted"])
        self.assertEqual(Harassment.objects.count(), 1)
        self.assertEqual(mocked_send_email.call_count, 1)

    def test_ctf_flow(self):
        ctf = Ctf.objects.create(
            title="Winter CTF",
            content="Solve me",
            start_date=timezone.now() - timezone.timedelta(hours=1),
            end_date=timezone.now() + timezone.timedelta(days=1),
            slug="winter-ctf",
            published=True,
        )
        Flag.objects.create(
            ctf=ctf,
            title="Flag 1",
            flag="flag{correct}",
            clues="Find it",
            slug="flag-1",
        )

        anonymous_response = self.client.get("/api/v1/ctf")
        self.assertEqual(anonymous_response.status_code, 403)

        self.client.login(username="tester", password="password123")

        list_response = self.client.get("/api/v1/ctf")
        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(len(list_response.json()["data"]), 1)

        detail_response = self.client.get("/api/v1/ctf/winter-ctf")
        self.assertEqual(detail_response.status_code, 200)
        self.assertEqual(len(detail_response.json()["data"]["flags"]), 1)

        invalid_guess_response = self.client.post(
            "/api/v1/ctf/winter-ctf/flag-1/guess",
            {"guess": "wrong"},
        )
        self.assertEqual(invalid_guess_response.status_code, 400)
        self.assertEqual(Guess.objects.count(), 1)

        valid_guess_response = self.client.post(
            "/api/v1/ctf/winter-ctf/flag-1/guess",
            {"guess": "flag{correct}"},
        )
        self.assertEqual(valid_guess_response.status_code, 200)
        self.assertTrue(valid_guess_response.json()["data"]["correct"])
        self.assertEqual(Guess.objects.filter(correct=True).count(), 1)

    def test_alumni_update_token_endpoint(self):
        token = AlumniUpdateToken.objects.create(email="alumni@example.com")
        response = self.client.get(f"/api/v1/alumni/update/{token.token}")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"]["email"], "alumni@example.com")

    def test_lucia_endpoint_disabled_for_date_association(self):
        response = self.client.get("/api/v1/lucia")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["error"]["code"], "feature_disabled")

    def test_account_activation_endpoint(self):
        new_user = Member.objects.create(
            username="inactive-user",
            email="inactive@example.com",
            membership_type=self.membership_type,
            is_active=False,
        )
        uid = urlsafe_base64_encode(force_bytes(new_user.pk))
        token = account_activation_token.make_token(new_user)

        response = self.client.get(f"/api/v1/auth/activate/{uid}/{token}")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["data"]["activated"])
        new_user.refresh_from_db()
        self.assertTrue(new_user.is_active)

    def test_archive_picture_collection_by_id_endpoint(self):
        collection = Collection.objects.create(
            title="Winter",
            type="Pictures",
            pub_date=timezone.now(),
        )
        self.client.login(username="tester", password="password123")
        response = self.client.get(f"/api/v1/archive/pictures/id/{collection.id}")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"]["collection"]["id"], collection.id)

    @patch("api.views.send_email_task.delay")
    def test_password_reset_and_confirm_flow(self, _mocked_send_email):
        reset_request = self.client.post("/api/v1/auth/password-reset", {"email": "tester@example.com"})
        self.assertEqual(reset_request.status_code, 200)
        self.assertTrue(reset_request.json()["data"]["submitted"])

        uid = urlsafe_base64_encode(force_bytes(self.member.pk))
        token = default_token_generator.make_token(self.member)
        reset_confirm = self.client.post(
            f"/api/v1/auth/password-reset/{uid}/{token}",
            {"new_password1": "newpass123A", "new_password2": "newpass123A"},
        )
        self.assertEqual(reset_confirm.status_code, 200)
        self.assertTrue(reset_confirm.json()["data"]["password_reset"])

    def test_password_change_when_authenticated(self):
        self.client.login(username="tester", password="password123")
        response = self.client.post(
            "/api/v1/auth/password-change",
            {
                "old_password": "password123",
                "new_password1": "changed123A",
                "new_password2": "changed123A",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["data"]["password_changed"])

    def test_news_feed_endpoint(self):
        response = self.client.get("/api/v1/news/feed")
        self.assertEqual(response.status_code, 200)

    def test_events_feed_endpoint(self):
        response = self.client.get("/api/v1/events/feed")
        self.assertEqual(response.status_code, 200)

    @override_settings(EXPERIMENTAL_FEATURES=["event_billing"])
    def test_meta_site_capabilities_include_event_billing_feature(self):
        response = self.client.get("/api/v1/meta/site")
        self.assertEqual(response.status_code, 200)
        capabilities = response.json()["data"]["module_capabilities"]
        self.assertIn("billing_status", capabilities["events"]["features"])
        self.assertIn("event_signup_billing", capabilities["billing"]["features"])

    @override_settings(EXPERIMENTAL_FEATURES=["event_billing"])
    @patch("billing.handlers.generate_invoice_number", return_value=24000099)
    @patch("billing.handlers.send_event_invoice")
    def test_event_signup_returns_billing_invoice_payload(self, _mocked_send_invoice, _mocked_invoice_number):
        event = Event.objects.create(
            title="Billing Event",
            slug="billing-event",
            author=self.member,
            sign_up=True,
            published=True,
            sign_up_members=timezone.now() - timezone.timedelta(hours=1),
            sign_up_others=timezone.now() - timezone.timedelta(hours=1),
            sign_up_deadline=timezone.now() + timezone.timedelta(days=1),
            event_date_start=timezone.now() + timezone.timedelta(days=1),
            event_date_end=timezone.now() + timezone.timedelta(days=1, hours=2),
        )
        EventBillingConfiguration.objects.create(
            event=event,
            due_date=datetime.date.today() + datetime.timedelta(days=14),
            integration_type=1,
            price="42",
            price_selector="",
        )

        response = self.client.post(
            f"/api/v1/events/{event.slug}/signup",
            {
                "user": "Billing User",
                "email": "billing-user@example.com",
                "anonymous": False,
            },
        )

        self.assertEqual(response.status_code, 201)
        payload = response.json()["data"]
        self.assertEqual(payload["event_slug"], event.slug)
        self.assertEqual(payload["billing"]["enabled"], True)
        self.assertEqual(payload["billing"]["status"], "invoice_created")
        self.assertEqual(payload["billing"]["invoice"]["invoice_number"], 24000099)
        self.assertEqual(payload["billing"]["invoice"]["amount"], 42.0)
        self.assertEqual(EventInvoice.objects.count(), 1)

    def test_event_detail_includes_template_variant(self):
        event = Event.objects.create(
            title="Arsfest",
            slug="arsfest26",
            author=self.member,
            sign_up=False,
            published=True,
            event_date_start=timezone.now() + timezone.timedelta(days=1),
            event_date_end=timezone.now() + timezone.timedelta(days=1, hours=2),
        )
        response = self.client.get(f"/api/v1/events/{event.slug}")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"]["template_variant"], "arsfest")

    def test_event_attendees_endpoint(self):
        event = Event.objects.create(
            title="Open Event",
            slug="open-event",
            author=self.member,
            sign_up=True,
            published=True,
            event_date_start=timezone.now() - timezone.timedelta(hours=2),
            event_date_end=timezone.now() + timezone.timedelta(hours=2),
            sign_up_max_participants=1,
        )
        EventRegistrationForm.objects.create(
            event=event,
            choice_number=10,
            name="allergies",
            type="text",
            required=False,
            public_info=True,
        )
        EventAttendees.objects.create(
            event=event,
            attendee_nr=10,
            user="Primary",
            email="primary@example.com",
            preferences={"allergies": "nuts"},
            anonymous=False,
            time_registered=timezone.now(),
        )
        EventAttendees.objects.create(
            event=event,
            attendee_nr=20,
            user="Secondary",
            email="secondary@example.com",
            preferences={"allergies": "none"},
            anonymous=True,
            time_registered=timezone.now(),
        )

        response = self.client.get(f"/api/v1/events/{event.slug}/attendees")
        self.assertEqual(response.status_code, 200)
        payload = response.json()["data"]
        self.assertEqual(payload["template_variant"], "default")
        self.assertEqual(payload["show_attendee_list"], True)
        self.assertEqual(payload["registration_public_fields"], ["allergies"])
        self.assertEqual(len(payload["attendees"]), 2)
        self.assertEqual(payload["attendees"][0]["display_name"], "Primary")
        self.assertEqual(payload["attendees"][1]["display_name"], "Anonymt")
        self.assertEqual(payload["attendees"][1]["is_waitlist"], True)
