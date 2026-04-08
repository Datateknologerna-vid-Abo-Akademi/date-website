import os
import subprocess

from django.apps import apps
from django.conf import settings
from django.contrib.admin.models import LogEntry
from django.core.management.base import BaseCommand
from django.db import connection
from django.db.models import Q
from django.db.utils import DatabaseError, OperationalError
from django.utils import timezone


class Command(BaseCommand):
    help = "Print a redacted production incident triage snapshot."

    def add_arguments(self, parser):
        parser.add_argument(
            "--limit",
            type=int,
            default=10,
            help="Number of rows to show for each section.",
        )

    def handle(self, *args, **options):
        limit = max(options["limit"], 1)

        self.print_runtime()
        self.print_blank_slugs(limit)
        self.print_recent_admin_edits(limit)

    def print_runtime(self):
        self.stdout.write(self.style.MIGRATE_HEADING("Runtime"))
        self.print_kv("time", timezone.now().isoformat())
        self.print_kv("project", getattr(settings, "PROJECT_NAME", "unknown"))
        self.print_kv("settings", settings.SETTINGS_MODULE)
        self.print_kv("debug", str(settings.DEBUG))
        self.print_kv("develop", str(getattr(settings, "DEVELOP", "unknown")))
        self.print_kv("database", connection.settings_dict["ENGINE"].rsplit(".", 1)[-1])
        self.print_kv("version", self.get_app_version())

    def print_blank_slugs(self, limit):
        self.stdout.write("")
        self.stdout.write(self.style.MIGRATE_HEADING("Blank Slugs"))
        slug_models = [
            ("events", "Event", ("id", "title", "published")),
            ("news", "Post", ("id", "title", "published")),
            ("news", "Category", ("id", "name")),
            ("staticpages", "StaticPage", ("id", "title")),
        ]

        found_any = False
        for app_label, model_name, fields in slug_models:
            model = self.get_model(app_label, model_name)
            if model is None:
                continue

            try:
                queryset = (
                    model.objects.filter(Q(slug__isnull=True) | Q(slug=""))
                    .values(*fields)[:limit]
                )
                rows = list(queryset)
            except (DatabaseError, OperationalError) as exc:
                self.stdout.write(self.style.WARNING(f"Blank slug check unavailable: {exc}"))
                return

            if not rows:
                continue

            found_any = True
            self.stdout.write(f"{app_label}.{model_name}:")
            for row in rows:
                self.stdout.write(f"  {row}")

        if not found_any:
            self.stdout.write("No blank slugs found.")

    def print_recent_admin_edits(self, limit):
        self.stdout.write("")
        self.stdout.write(self.style.MIGRATE_HEADING("Recent Admin Edits"))

        try:
            entries = list(
                LogEntry.objects.select_related("user", "content_type")
                .order_by("-action_time")[:limit]
            )
        except (DatabaseError, OperationalError) as exc:
            self.stdout.write(self.style.WARNING(f"Recent admin edits unavailable: {exc}"))
            return

        if not entries:
            self.stdout.write("No admin edits found.")
            return

        for entry in entries:
            user = getattr(entry.user, "username", None) or str(entry.user_id)
            content_type = entry.content_type.app_label + "." + entry.content_type.model
            self.stdout.write(
                f"{entry.action_time.isoformat()} user={user} "
                f"action={entry.get_action_flag_display()} object={content_type}:{entry.object_id} "
                f"repr={entry.object_repr} changes={entry.change_message}"
            )

    def get_model(self, app_label, model_name):
        try:
            return apps.get_model(app_label, model_name)
        except LookupError:
            return None

    def get_app_version(self):
        for env_name in ("APP_VERSION", "GIT_COMMIT", "SOURCE_VERSION", "DATE_IMG_TAG"):
            value = os.environ.get(env_name)
            if value:
                return f"{env_name}={value}"

        try:
            return subprocess.check_output(
                ["git", "rev-parse", "--short", "HEAD"],
                text=True,
                stderr=subprocess.DEVNULL,
                timeout=1,
            ).strip()
        except Exception:
            return "unavailable"

    def print_kv(self, key, value):
        self.stdout.write(f"{key}: {value}")
