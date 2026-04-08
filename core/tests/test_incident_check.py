from io import StringIO

from django.contrib.admin.models import CHANGE, LogEntry
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.core.management import call_command
from django.test import TestCase

from events.models import Event


class IncidentCheckCommandTests(TestCase):
    def test_outputs_runtime_blank_slugs_and_recent_admin_edits(self):
        user = get_user_model().objects.create_user(username="incident-admin")
        event = Event.objects.create(title="Broken Event", slug="", author=user)
        content_type = ContentType.objects.get_for_model(Event)
        LogEntry.objects.log_action(
            user_id=user.pk,
            content_type_id=content_type.pk,
            object_id=event.pk,
            object_repr=str(event),
            action_flag=CHANGE,
            change_message="Changed title.",
        )

        output = StringIO()
        call_command("incident_check", "--limit", "5", stdout=output)
        text = output.getvalue()

        self.assertIn("Runtime", text)
        self.assertIn("debug:", text)
        self.assertIn("Blank Slugs", text)
        self.assertIn("events.Event", text)
        self.assertIn("Broken Event", text)
        self.assertIn("Recent Admin Edits", text)
        self.assertIn("incident-admin", text)

    def test_does_not_dump_sensitive_settings(self):
        output = StringIO()
        call_command("incident_check", stdout=output)
        text = output.getvalue()

        self.assertNotIn("SECRET_KEY", text)
        self.assertNotIn("ALUMNI_SETTINGS", text)
        self.assertNotIn("AWS_SECRET_ACCESS_KEY", text)
