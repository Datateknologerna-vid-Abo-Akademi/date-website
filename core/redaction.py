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
