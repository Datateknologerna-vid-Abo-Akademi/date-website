from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from alumni.models import AlumniUpdateToken
from ctf.models import Ctf, Flag, Guess
from members.models import MembershipType, Member
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
