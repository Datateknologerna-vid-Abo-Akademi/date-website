"""Replace report text stored in admin log entries with a content-free label.

Until ``Harassment.__str__`` stopped returning the report, Django stored the
beginning of the report text in ``django_admin_log.object_repr`` for every admin
add, change, and delete. ``harassment/migrations/0002_redact_admin_log_reports.py``
rewrites the rows that existed when the release with that change ran, which covers
every row written before the deploy.

Migrations run before the application rolls and a blue-green standby shares the
database with the live release, so a pod still running the older image can write
one more content-bearing row after the migration has passed. Run this command
once the old pods are gone to redact those rows; it is safe to run at any time
and reports nothing to redact when the log is already clean.
"""

from django.contrib.admin.models import LogEntry
from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand

from harassment.redaction import REPORT_CONTENT_TYPES, report_label


class Command(BaseCommand):
    help = "Replace harassment report text in admin log entries with a content-free label."

    def handle(self, *args, **options):
        redacted = 0

        for app_label, model in sorted(REPORT_CONTENT_TYPES):
            content_type = ContentType.objects.filter(app_label=app_label, model=model).first()
            if content_type is None:
                continue

            for entry in LogEntry.objects.filter(content_type=content_type).iterator():
                label = report_label(entry.object_id)
                if entry.object_repr == label:
                    continue
                entry.object_repr = label
                entry.save(update_fields=["object_repr"])
                redacted += 1

        self.stdout.write(self.style.SUCCESS(f"Redacted {redacted} admin log entries."))
