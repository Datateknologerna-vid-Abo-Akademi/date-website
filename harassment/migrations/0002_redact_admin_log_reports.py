"""Redact harassment report text that earlier releases copied into the admin log.

Django stores ``str(obj)[:200]`` in ``django_admin_log.object_repr`` for every
add, change, and delete. Until ``Harassment.__str__`` stopped returning the
report, that column held the beginning of the report text, and the admin log
page rendered it for any staff member allowed to view log entries. This
migration replaces those stored strings with the content-free label.
"""

from django.db import migrations
from django.db.models import F, Value
from django.db.models.functions import Concat

# Reports written before the harassment app was split out carry the old "social"
# app label. The content type still exists in databases migrated from that
# schema, so both labels are redacted.
REPORT_CONTENT_TYPES = (
    ("harassment", "harassment"),
    ("social", "harassment"),
)

# Mirrors harassment.redaction.REPORT_CONTENT_TYPES and report_label. Kept
# inline so the migration does not depend on application code that may change
# later; the label is not translated, so the format is stable.
REDACTED_LABEL_PREFIX = "Trakasserianmälan #"


def redact_report_log_entries(apps, schema_editor):
    log_entry = apps.get_model("admin", "LogEntry")
    content_type = apps.get_model("contenttypes", "ContentType")

    for app_label, model in REPORT_CONTENT_TYPES:
        type_id = (
            content_type.objects.filter(app_label=app_label, model=model)
            .values_list("pk", flat=True)
            .first()
        )
        if type_id is None:
            continue

        log_entry.objects.filter(content_type_id=type_id).update(
            object_repr=Concat(Value(REDACTED_LABEL_PREFIX), F("object_id")),
        )


class Migration(migrations.Migration):

    # The data migration reads django_admin_log, which the admin app creates, and
    # migrations have no ordering guarantee without this dependency.
    dependencies = [
        ("harassment", "0001_initial"),
        ("admin", "0003_logentry_add_action_flag_choices"),
    ]

    operations = [
        migrations.RunPython(redact_report_log_entries, migrations.RunPython.noop),
    ]
