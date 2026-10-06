from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse

from harassment.models import Harassment, HarassmentEmailRecipient


class HarassmentViewTests(TestCase):
    def setUp(self):
        HarassmentEmailRecipient.objects.create(recipient_email="admin@example.com")

    @patch("harassment.views.send_email_task")
    @patch("harassment.views.validate_captcha", return_value=True)
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

    @patch("harassment.views.send_email_task")
    @patch("harassment.views.validate_captcha", return_value=True)
    def test_success_page_is_shown_on_the_get_after_a_submission(self, _mock_validate_captcha, _mock_send_email):
        self.client.post(
            reverse("social:harassment"),
            {
                "email": "reporter@example.com",
                "message": "Something happened",
                "cf-turnstile-response": "token",
            },
        )

        response = self.client.get(reverse("social:harassment"))
        self.assertContains(response, "Tack för att du rapporterade.")

        # That GET consumed the one-shot flag: the next GET is the form again.
        again = self.client.get(reverse("social:harassment"))
        self.assertContains(again, "Beskrivning av händelsen")
        self.assertNotContains(again, "Tack för att du rapporterade.")

    @patch("harassment.views.send_email_task")
    @patch("harassment.views.validate_captcha", return_value=True)
    def test_post_while_the_success_flag_is_set_is_still_saved(self, _mock_validate_captcha, _mock_send_email):
        # The redirect GET never landed (back button, dropped connection, a
        # second tab), so the flag is still in the session when the next report
        # is submitted. That POST must be validated and saved, not answered
        # with the thank-you page while dropping the report.
        session = self.client.session
        session["harass_submitted"] = True
        session.save()

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
        self.assertEqual(Harassment.objects.get().message, "Something happened")
