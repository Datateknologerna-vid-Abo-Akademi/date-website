"""Content-free labels for harassment reports.

Report text is stored in full on :class:`harassment.models.Harassment`, and
Django copies ``str(obj)[:200]`` into ``django_admin_log.object_repr`` for every
add, change, and delete. The admin log is readable by staff who are not report
recipients, so a report is labelled by primary key only: whoever may read the log
learns that a report was touched, never what it said.

The label is deliberately not translated. It is written into the database as an
audit record, so it must not depend on the language that happened to be active
when the row was logged: a stable value keeps rows comparable and lets the
cleanup command in ``harassment/management/commands/redact_harassment_logs.py``
recognise an already-redacted row with an exact comparison.
"""

__all__ = ["REPORT_CONTENT_TYPES", "report_label"]

# Content types whose log entries can hold report text. "social" is the app
# label reports carried before the harassment app was split out.
REPORT_CONTENT_TYPES = frozenset(
    {
        ("harassment", "harassment"),
        ("social", "harassment"),
    }
)


def report_label(report_id):
    """Return the label used for a report wherever it is identified."""
    return f"Trakasserianmälan #{report_id}"
