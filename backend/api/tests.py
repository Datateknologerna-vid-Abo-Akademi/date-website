from unittest.mock import patch

from django.contrib.auth.tokens import default_token_generator
from django.test import TestCase
from django.utils import timezone
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from alumni.models import AlumniUpdateToken
from archive.models import Collection
from ctf.models import Ctf, Flag, Guess
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
        self.assertIn("data", response.json())

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
