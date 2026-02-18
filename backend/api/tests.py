from django.test import TestCase

from members.models import MembershipType, Member


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
