from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse

from social.models import Harassment, HarassmentEmailRecipient


class HarassmentViewTests(TestCase):
    def setUp(self):
        HarassmentEmailRecipient.objects.create(recipient_email="admin@example.com")

    @patch("social.views.send_email_task")
    @patch("social.views.validate_captcha", return_value=True)
    def test_valid_submission_saves_report_and_enqueues_email_on_commit(
        self,
        _mock_validate_captcha,
        mock_send_email,
    ):
        with self.captureOnCommitCallbacks(execute=True) as callbacks:
            response = self.client.post(
                reverse("social:harassment"),
                {
                    "email": "reporter@example.com",
                    "message": "Something happened",
                    "cf-turnstile-response": "token",
                },
            )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(Harassment.objects.count(), 1)
        self.assertEqual(len(callbacks), 1)
        mock_send_email.delay.assert_called_once()
