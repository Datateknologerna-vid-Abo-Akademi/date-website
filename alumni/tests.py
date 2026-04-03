from unittest.mock import MagicMock, patch

from django.utils import timezone
from django.test import TestCase, override_settings
from django.urls import reverse

from alumni.config import get_alumni_sheet_config
from alumni.models import AlumniUpdateToken
from alumni.tasks import get_sheet_client


class AlumniConfigTests(TestCase):
    @override_settings(ALUMNI_SETTINGS="")
    def test_empty_alumni_settings_returns_empty_config(self):
        auth, sheet = get_alumni_sheet_config()
        self.assertEqual(auth, {})
        self.assertEqual(sheet, "")

    @override_settings(ALUMNI_SETTINGS="not-json")
    def test_invalid_alumni_settings_returns_empty_config_and_logs(self):
        with self.assertLogs("date", level="ERROR") as logs:
            auth, sheet = get_alumni_sheet_config()

        self.assertEqual(auth, {})
        self.assertEqual(sheet, "")
        self.assertTrue(any("Error while loading alumni settings" in message for message in logs.output))

    @override_settings(ALUMNI_SETTINGS='{"auth": {"client_email": "bot@example.com"}, "sheet": "sheet-id"}')
    def test_valid_alumni_settings_returns_auth_and_sheet(self):
        auth, sheet = get_alumni_sheet_config()
        self.assertEqual(auth, {"client_email": "bot@example.com"})
        self.assertEqual(sheet, "sheet-id")


class AlumniViewRegressionTests(TestCase):
    @override_settings(ALUMNI_SETTINGS="")
    def test_signup_page_renders_without_alumni_settings(self):
        response = self.client.get(reverse("alumni:alumni_signup"))
        self.assertEqual(response.status_code, 200)

    @override_settings(ALUMNI_SETTINGS="not-json")
    def test_update_verify_page_renders_with_invalid_alumni_settings(self):
        response = self.client.get(reverse("alumni:alumni_update"))
        self.assertEqual(response.status_code, 200)

    @override_settings(ALUMNI_SETTINGS="not-json")
    @patch("alumni.views.handle_alumni_signup.delay")
    @patch("alumni.views.validate_captcha", return_value=True)
    @patch("alumni.views.DateSheetsAdapter")
    def test_signup_post_uses_lazy_loaded_empty_sheet_config_for_invalid_settings(
        self,
        mock_adapter,
        _mock_validate_captcha,
        mock_handle_alumni_signup,
    ):
        adapter_instance = MagicMock()
        adapter_instance.get_column_by_name.return_value = 1
        adapter_instance.get_column_values.return_value = []
        mock_adapter.return_value = adapter_instance

        with self.assertLogs("date", level="ERROR") as logs:
            response = self.client.post(
                reverse("alumni:alumni_signup"),
                {
                    "operation": "CREATE",
                    "firstname": "Ada",
                    "lastname": "Lovelace",
                    "email": "ada@example.com",
                    "cf-turnstile-response": "test-token",
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(any("Error while loading alumni settings" in message for message in logs.output))
        mock_adapter.assert_called_once_with({}, "", "members")
        mock_handle_alumni_signup.assert_called_once()

    @override_settings(ALUMNI_SETTINGS='{"auth": {"client_email": "bot@example.com"}, "sheet": "sheet-id"}')
    @patch("alumni.views.handle_alumni_signup.delay")
    @patch("alumni.views.validate_captcha", return_value=True)
    @patch("alumni.views.DateSheetsAdapter")
    def test_signup_post_queues_task_when_email_not_registered(
        self,
        mock_adapter,
        _mock_validate_captcha,
        mock_handle_alumni_signup,
    ):
        adapter_instance = MagicMock()
        adapter_instance.get_column_by_name.return_value = 1
        adapter_instance.get_column_values.return_value = []
        mock_adapter.return_value = adapter_instance

        response = self.client.post(
            reverse("alumni:alumni_signup"),
            {
                "operation": "CREATE",
                "firstname": "Ada",
                "lastname": "Lovelace",
                "email": "ada@example.com",
                "cf-turnstile-response": "test-token",
            },
        )

        self.assertEqual(response.status_code, 200)
        mock_adapter.assert_called_once_with({"client_email": "bot@example.com"}, "sheet-id", "members")
        mock_handle_alumni_signup.assert_called_once()
        payload = mock_handle_alumni_signup.call_args.args[0]
        self.assertEqual(payload["operation"], "CREATE")
        self.assertEqual(payload["firstname"], "Ada")
        self.assertEqual(payload["lastname"], "Lovelace")
        self.assertEqual(payload["email"], "ada@example.com")
        self.assertEqual(payload["token"], "")

    def test_update_form_renders_for_valid_token(self):
        token = AlumniUpdateToken.objects.create(email="ada@example.com")

        response = self.client.get(reverse("alumni:alumni_update_with_token", args=[token.token]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "ada@example.com")

    def test_update_form_redirects_for_expired_token(self):
        token = AlumniUpdateToken.objects.create(email="expired@example.com")
        token.created_at = timezone.now() - timezone.timedelta(hours=25)
        token.save(update_fields=["created_at"])

        response = self.client.get(reverse("alumni:alumni_update_with_token", args=[token.token]))

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["Location"], reverse("alumni:alumni_update"))

    @patch("alumni.views.handle_alumni_signup.delay")
    def test_update_form_post_queues_task_for_valid_token(self, mock_handle_alumni_signup):
        token = AlumniUpdateToken.objects.create(email="ada@example.com")

        response = self.client.post(
            reverse("alumni:alumni_update_with_token", args=[token.token]),
            {
                "firstname": "Ada",
                "lastname": "Lovelace",
                "city": "Turku",
            },
        )

        self.assertEqual(response.status_code, 200)
        mock_handle_alumni_signup.assert_called_once()
        payload = mock_handle_alumni_signup.call_args.args[0]
        self.assertEqual(payload["operation"], "UPDATE")
        self.assertEqual(payload["email"], "ada@example.com")
        self.assertEqual(str(payload["token"]), str(token.token))
        self.assertEqual(payload["city"], "Turku")

    @patch("alumni.views.send_token_email.delay")
    @patch("alumni.views.validate_captcha", return_value=True)
    def test_update_verify_post_creates_token_and_sends_email(self, _mock_validate_captcha, mock_send_token_email):
        response = self.client.post(
            reverse("alumni:alumni_update"),
            {
                "email": "ada@example.com",
                "cf-turnstile-response": "test-token",
            },
        )

        self.assertEqual(response.status_code, 200)
        token = AlumniUpdateToken.objects.get(email="ada@example.com")
        mock_send_token_email.assert_called_once_with(token.token, "ada@example.com")


class AlumniTaskRegressionTests(TestCase):
    @patch("alumni.tasks.DateSheetsAdapter")
    @patch("alumni.tasks.get_alumni_sheet_config", return_value=({"client_email": "bot@example.com"}, "sheet-id"))
    def test_get_sheet_client_uses_lazy_loaded_config(self, mock_get_config, mock_adapter):
        client = get_sheet_client("members")

        mock_get_config.assert_called_once_with()
        mock_adapter.assert_called_once_with({"client_email": "bot@example.com"}, "sheet-id", "members")
        self.assertEqual(client, mock_adapter.return_value)
