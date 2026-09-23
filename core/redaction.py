import asyncio
import logging
import re

from django.views.debug import SafeExceptionReporterFilter

REDACTED = "********************"


class DateExceptionReporterFilter(SafeExceptionReporterFilter):
    hidden_settings = re.compile(
        SafeExceptionReporterFilter.hidden_settings.pattern
        + "|ALUMNI|CREDENTIAL|PRIVATE|SERVICE_ACCOUNT|CLIENT_EMAIL|CLIENT_ID",
        flags=re.I,
    )


class ShieldedFutureCancellationFilter(logging.Filter):
    """Drop the benign cancellation records Python 3.14 logs for shielded futures.

    Since Python 3.14, ``asyncio.shield()`` registers an exception handler on
    the future it wraps, and logs an exception that nobody retrieves through the
    event loop exception handler at ERROR. When an ASGI client disconnects
    mid-request, asgiref's sync bridge is often awaiting ``asyncio.shield(...)``,
    so the shielded future finishes with an ``asyncio.CancelledError`` and the
    record carries the whole inner request traceback. Cancelling a request
    because the client went away is normal, so those records are dropped.

    A shielded future that fails with any other exception is kept: a
    never-retrieved exception there is a genuine problem.
    """

    shielded_future_message = re.compile(r"exception in shielded future")

    def filter(self, record):
        try:
            message = record.getMessage()
        except Exception:
            # A filter must never raise: logging would break for the caller.
            return True

        if not self.shielded_future_message.search(message):
            return True

        # Only well-formed logger exception info is dropped. A malformed tuple
        # that happens to carry a cancellation must still be kept.
        exc_info = getattr(record, "exc_info", None)
        if not isinstance(exc_info, tuple) or len(exc_info) != 3:
            return True

        exception_type = exc_info[0]
        if not isinstance(exception_type, type) or not issubclass(exception_type, asyncio.CancelledError):
            return True

        return not isinstance(exc_info[1], asyncio.CancelledError)


class RedactingFormatter(logging.Formatter):
    private_key_block = re.compile(
        r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----",
        flags=re.I | re.S,
    )
    sensitive_json_value = re.compile(
        r"(?P<prefix>[\"']?(?:private_key|private_key_id|client_email|client_id|service_account|credentials)[\"']?\s*[:=]\s*[\"'])"
        r"(?P<value>.*?)(?P<suffix>[\"'])",
        flags=re.I,
    )
    alumni_settings_value = re.compile(
        r"(?P<prefix>ALUMNI_SETTINGS\s*[:=]\s*)(?P<value>.+)",
        flags=re.I,
    )

    @classmethod
    def redact(cls, text):
        text = cls.private_key_block.sub(REDACTED, text)
        text = cls.sensitive_json_value.sub(
            rf"\g<prefix>{REDACTED}\g<suffix>",
            text,
        )
        return cls.alumni_settings_value.sub(
            rf"\g<prefix>{REDACTED}",
            text,
        )

    def format(self, record):
        return self.redact(super().format(record))


def redact_text(text):
    return RedactingFormatter.redact(str(text))
