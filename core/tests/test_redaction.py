import logging

from django.conf import settings
from django.test import SimpleTestCase

from core.redaction import (
    DateExceptionReporterFilter,
    REDACTED,
    RedactingFormatter,
    redact_text,
)


class DateExceptionReporterFilterTests(SimpleTestCase):
    def test_masks_alumni_settings(self):
        exception_filter = DateExceptionReporterFilter()

        self.assertEqual(
            exception_filter.cleanse_setting("ALUMNI_SETTINGS", '{"private_key": "secret"}'),
            REDACTED,
        )

    def test_masks_service_account_identifiers_in_nested_settings(self):
        exception_filter = DateExceptionReporterFilter()

        cleansed = exception_filter.cleanse_setting(
            "GOOGLE_SETTINGS",
            {
                "client_email": "service-account@example.com",
                "client_id": "123456",
                "regular_setting": "visible",
            },
        )

        self.assertEqual(cleansed["client_email"], REDACTED)
        self.assertEqual(cleansed["client_id"], REDACTED)
        self.assertEqual(cleansed["regular_setting"], "visible")


class RedactingFormatterTests(SimpleTestCase):
    def format_message(self, message, *args):
        formatter = RedactingFormatter("%(levelname)s %(message)s")
        record = logging.LogRecord(
            name="test",
            level=logging.ERROR,
            pathname=__file__,
            lineno=1,
            msg=message,
            args=args,
            exc_info=None,
        )
        return formatter.format(record)

    def test_redacts_alumni_settings_log_message(self):
        output = self.format_message(
            'ALUMNI_SETTINGS=%s',
            '{"private_key":"secret-key","client_email":"service@example.com"}',
        )

        self.assertIn(REDACTED, output)
        self.assertNotIn("secret-key", output)
        self.assertNotIn("service@example.com", output)

    def test_redacts_private_key_blocks(self):
        output = self.format_message(
            'private_key="-----BEGIN PRIVATE KEY-----secret-key-----END PRIVATE KEY-----"'
        )

        self.assertIn(REDACTED, output)
        self.assertNotIn("secret-key", output)

    def test_redact_text_uses_formatter_redaction_rules(self):
        output = redact_text('client_email="service@example.com"')

        self.assertIn(REDACTED, output)
        self.assertNotIn("service@example.com", output)


class LoggingSettingsTests(SimpleTestCase):
    def test_django_console_handler_does_not_override_logger_level(self):
        self.assertEqual(settings.LOGGING["handlers"]["console"]["level"], "NOTSET")
