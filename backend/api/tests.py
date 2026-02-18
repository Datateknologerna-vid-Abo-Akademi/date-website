from django.test import TestCase


class ApiSmokeTests(TestCase):
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
