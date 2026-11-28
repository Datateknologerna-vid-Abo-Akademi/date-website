import asyncio
import copy
import logging
from contextlib import contextmanager
from logging.config import DictConfigurator

from django.test import SimpleTestCase

from core.redaction import (
    REDACTED,
    DateExceptionReporterFilter,
    RedactingFormatter,
    ShieldedFutureCancellationFilter,
    redact_text,
)


def make_record(msg, args=(), exc_info=None, level=logging.ERROR, name="asyncio"):
    # LogRecord stores exc_info verbatim; Logger._log normalizes a bare
    # exception into a (type, value, traceback) tuple before creating the
    # record. Mirror that here so the records match what logging really emits.
    if isinstance(exc_info, BaseException):
        exc_info = (type(exc_info), exc_info, exc_info.__traceback__)
    return logging.LogRecord(
        name=name,
        level=level,
        pathname=__file__,
        lineno=1,
        msg=msg,
        args=args,
        exc_info=exc_info,
    )


@contextmanager
def project_asyncio_logging():
    """Apply the project's 'asyncio' logger entry from the real LOGGING config.

    ``logging.config.dictConfig`` cannot be used here directly: it clears and
    closes every handler registered with the logging module, which would tear
    down the test suite's own logging setup. Resolving the real config with a
    ``DictConfigurator`` and applying only the 'asyncio' logger exercises the
    project configuration without disturbing the rest of the process.
    """
    from core.settings import common

    raw = copy.deepcopy(common.LOGGING)
    configurator = DictConfigurator(raw)
    # DictConfigurator copies the config into its own ConvertingDict, so the
    # resolved objects have to be installed on configurator.config for handler
    # and logger resolution to find them.
    config = configurator.config
    config["formatters"] = {name: configurator.configure_formatter(spec) for name, spec in raw["formatters"].items()}
    config["filters"] = {name: configurator.configure_filter(spec) for name, spec in raw["filters"].items()}
    config["handlers"] = {name: configurator.configure_handler(spec) for name, spec in raw["handlers"].items()}

    logger = logging.getLogger("asyncio")
    saved = (logger.handlers[:], logger.filters[:], logger.level, logger.propagate, logger.disabled)
    try:
        configurator.configure_logger("asyncio", raw["loggers"]["asyncio"])
        yield logger
    finally:
        handlers, filters, level, propagate, disabled = saved
        logger.handlers = handlers
        logger.filters = filters
        logger.setLevel(level)
        logger.propagate = propagate
        logger.disabled = disabled


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
        output = self.format_message('private_key="-----BEGIN PRIVATE KEY-----secret-key-----END PRIVATE KEY-----"')

        self.assertIn(REDACTED, output)
        self.assertNotIn("secret-key", output)

    def test_redact_text_uses_formatter_redaction_rules(self):
        output = redact_text('client_email="service@example.com"')

        self.assertIn(REDACTED, output)
        self.assertNotIn("service@example.com", output)


class ShieldedFutureCancellationFilterTests(SimpleTestCase):
    def setUp(self):
        self.log_filter = ShieldedFutureCancellationFilter()

    def test_drops_shielded_future_cancellation(self):
        record = make_record(
            "CancelledError exception in shielded future",
            exc_info=asyncio.CancelledError(),
        )

        self.assertFalse(self.log_filter.filter(record))

    def test_drops_shielded_future_cancellation_with_message_details(self):
        # The real record continues with 'future: ...' on the next line.
        record = make_record(
            "CancelledError exception in shielded future\nfuture: <Future finished exception=CancelledError()>",
            exc_info=asyncio.CancelledError(),
        )

        self.assertFalse(self.log_filter.filter(record))

    def test_keeps_shielded_future_with_other_exception(self):
        record = make_record(
            "Resolver404 exception in shielded future",
            exc_info=RuntimeError("boom"),
        )

        self.assertTrue(self.log_filter.filter(record))

    def test_keeps_unrelated_asyncio_error(self):
        record = make_record("Task exception was never retrieved", exc_info=RuntimeError("boom"))

        self.assertTrue(self.log_filter.filter(record))

    def test_keeps_shielded_future_message_without_exc_info(self):
        record = make_record("CancelledError exception in shielded future", exc_info=None)

        self.assertTrue(self.log_filter.filter(record))

    def test_keeps_shielded_future_message_with_non_exception_exc_info(self):
        record = make_record(
            "CancelledError exception in shielded future",
            exc_info=(None, "not an exception", None),
        )

        self.assertTrue(self.log_filter.filter(record))

    def test_keeps_shielded_future_message_with_malformed_exc_info(self):
        for exc_info in ("not a tuple", ("only-one-element",)):
            with self.subTest(exc_info=exc_info):
                record = make_record(
                    "CancelledError exception in shielded future",
                    exc_info=exc_info,
                )

                self.assertTrue(self.log_filter.filter(record))

    def test_keeps_shielded_future_message_with_malformed_full_length_exc_info(self):
        # A full-length tuple whose middle element is a cancellation is still not
        # logger-produced exception information, so the record must be kept.
        for exc_info in (
            (None, asyncio.CancelledError(), None),
            (RuntimeError, asyncio.CancelledError(), None),
            ("asyncio.CancelledError", asyncio.CancelledError(), None),
        ):
            with self.subTest(exc_info=exc_info):
                record = make_record(
                    "CancelledError exception in shielded future",
                    exc_info=exc_info,
                )

                self.assertTrue(self.log_filter.filter(record))

    def test_drops_shielded_future_cancellation_with_normalized_exc_info(self):
        # Logger._log normalizes the exception into (type, value, traceback);
        # this well-formed form is the production record and stays dropped.
        record = make_record(
            "CancelledError exception in shielded future",
            exc_info=(asyncio.CancelledError, asyncio.CancelledError(), None),
        )

        self.assertFalse(self.log_filter.filter(record))

    def test_keeps_record_when_message_cannot_be_formatted(self):
        # getMessage() raises TypeError because the message has no placeholders;
        # the filter must keep the record instead of breaking logging.
        record = make_record("no placeholders here", args=("unexpected",))

        self.assertTrue(self.log_filter.filter(record))


class AsyncioLoggerConfigTests(SimpleTestCase):
    def test_project_config_attaches_filter_to_asyncio_logger(self):
        from core.settings import common

        self.assertIn("shielded_future_cancellation", common.LOGGING["filters"])
        entry = common.LOGGING["loggers"]["asyncio"]
        self.assertIn("shielded_future_cancellation", entry["filters"])
        self.assertNotEqual(entry["level"], "CRITICAL")
        self.assertEqual(entry["handlers"], ["console"])

    def test_project_config_drops_shielded_future_cancellation(self):
        with project_asyncio_logging():
            with self.assertNoLogs("asyncio", level="ERROR"):
                logging.getLogger("asyncio").error(
                    "CancelledError exception in shielded future",
                    exc_info=asyncio.CancelledError(),
                )

    def test_project_config_keeps_genuine_asyncio_error(self):
        with project_asyncio_logging():
            with self.assertLogs("asyncio", level="ERROR") as captured:
                logging.getLogger("asyncio").error(
                    "Task exception was never retrieved",
                    exc_info=RuntimeError("boom"),
                )

        self.assertTrue(any("Task exception was never retrieved" in line for line in captured.output))


class LoggingSettingsTests(SimpleTestCase):
    def test_django_console_handler_does_not_override_logger_level(self):
        from core.settings.common import LOGGING

        self.assertEqual(LOGGING["handlers"]["console"]["level"], "NOTSET")
