from io import StringIO
from unittest.mock import MagicMock, patch

from django.contrib.admin.models import CHANGE, LogEntry
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.core.management import call_command
from django.test import TestCase

from date.management.commands.incident_check import Command
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

    def test_blank_slugs_are_sorted_by_descending_id(self):
        fake_model = MagicMock()
        filtered = fake_model.objects.filter.return_value
        ordered = filtered.order_by.return_value
        valued = ordered.values.return_value
        valued.__getitem__.return_value = [{"id": 2, "title": "Latest", "published": True}]

        output = StringIO()
        command = Command(stdout=output)

        with patch.object(Command, "get_model", side_effect=[fake_model, None, None, None]):
            command.print_blank_slugs(limit=2)

        filtered.order_by.assert_called_once_with("-id")
        ordered.values.assert_called_once_with("id", "title", "published")

    def test_admin_edit_fields_are_redacted_before_output(self):
        user = get_user_model().objects.create_user(username="redacted-admin")
        event = Event.objects.create(title="Sensitive Event", slug="", author=user)
        content_type = ContentType.objects.get_for_model(Event)
        LogEntry.objects.log_action(
            user_id=user.pk,
            content_type_id=content_type.pk,
            object_id=event.pk,
            object_repr='client_email="service@example.com"',
            action_flag=CHANGE,
            change_message='ALUMNI_SETTINGS={"private_key":"secret-key"}',
        )

        output = StringIO()
        call_command("incident_check", "--limit", "5", stdout=output)
        text = output.getvalue()

        self.assertIn("repr=client_email=", text)
        self.assertIn("changes=ALUMNI_SETTINGS=", text)
        self.assertIn("********************", text)
        self.assertNotIn("service@example.com", text)
        self.assertNotIn("secret-key", text)

    def test_does_not_dump_sensitive_settings(self):
        output = StringIO()
        call_command("incident_check", stdout=output)
        text = output.getvalue()

        self.assertNotIn("SECRET_KEY", text)
        self.assertNotIn("ALUMNI_SETTINGS", text)
        self.assertNotIn("AWS_SECRET_ACCESS_KEY", text)
