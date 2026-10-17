from __future__ import annotations

import importlib
from io import StringIO
from types import SimpleNamespace
from unittest.mock import Mock

from django.apps import apps
from django.conf import settings
from django.contrib import admin
from django.contrib.admin.models import ADDITION, LogEntry
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.contrib.messages import get_messages
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from harassment.admin import HarassmentAdmin, HarassmentEmailRecipientAdmin
from harassment.models import Harassment, HarassmentEmailRecipient

# Distinctive enough that a leak cannot be confused with unrelated page text.
REPORT_TEXT = "En unik beskrivning som aldrig får hamna i administrationsloggen"


class HarassmentLegacyAdminPermissionTests(TestCase):
    def test_legacy_social_permissions_preserve_admin_access(self):
        request = SimpleNamespace(
            user=SimpleNamespace(
                has_module_perms=Mock(return_value=False),
                has_perm=Mock(side_effect=lambda permission: permission.startswith('social.')),
            )
        )

        report_admin = HarassmentAdmin(Harassment, admin.site)
        recipient_admin = HarassmentEmailRecipientAdmin(HarassmentEmailRecipient, admin.site)

        self.assertTrue(report_admin.has_module_permission(request))
        self.assertTrue(report_admin.has_view_permission(request))
        self.assertTrue(recipient_admin.has_change_permission(request))


class HarassmentAdminLogRedactionTests(TestCase):
    """Report text must never reach the admin log, which non-recipients can read."""

    @classmethod
    def setUpTestData(cls):
        cls.admin_user = get_user_model().objects.create_superuser(
            username='harassmentlogadmin',
            email='harassmentlogadmin@example.com',
            password='pass',
        )

    def setUp(self):
        self.client.force_login(self.admin_user, backend='members.backends.AuthBackend')

    def create_report(self):
        return Harassment.objects.create(email='reporter@example.com', message=REPORT_TEXT)

    def assert_log_entries_have_no_report_text(self):
        entries = list(LogEntry.objects.all())
        self.assertTrue(entries)
        for entry in entries:
            self.assertNotIn(REPORT_TEXT, entry.object_repr)
            self.assertNotIn(REPORT_TEXT, entry.change_message)
            self.assertNotIn(REPORT_TEXT, entry.get_change_message())

    def test_str_identifies_the_report_without_its_content(self):
        report = self.create_report()

        label = str(report)

        self.assertNotIn(REPORT_TEXT, label)
        self.assertIn(f'#{report.pk}', label)

    def test_admin_add_change_and_delete_keep_report_text_out_of_the_log(self):
        response = self.client.post(
            reverse('admin:harassment_harassment_add'),
            {'email': 'reporter@example.com', 'message': REPORT_TEXT, '_save': 'Save'},
        )
        self.assertEqual(response.status_code, 302)
        report = Harassment.objects.get()

        response = self.client.post(
            reverse('admin:harassment_harassment_change', args=[report.pk]),
            {'email': 'reporter@example.com', 'message': f'{REPORT_TEXT} (uppdaterad)', '_save': 'Save'},
        )
        self.assertEqual(response.status_code, 302)

        response = self.client.post(
            reverse('admin:harassment_harassment_delete', args=[report.pk]),
            {'post': 'yes'},
        )
        self.assertEqual(response.status_code, 302)

        self.assertEqual(LogEntry.objects.count(), 3)
        self.assert_log_entries_have_no_report_text()

    def test_admin_log_page_does_not_render_report_text(self):
        report = self.create_report()
        response = self.client.post(
            reverse('admin:harassment_harassment_change', args=[report.pk]),
            {'email': 'reporter@example.com', 'message': REPORT_TEXT, '_save': 'Save'},
        )
        self.assertEqual(response.status_code, 302)

        response = self.client.get(reverse('admin:admin_logentry_changelist'))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, REPORT_TEXT)
        self.assertContains(response, f'#{report.pk}')

    def test_no_admin_surface_renders_report_text(self):
        """Log list, log detail, both history pages, and the dashboard."""
        report = self.create_report()
        self.client.post(
            reverse('admin:harassment_harassment_change', args=[report.pk]),
            {'email': 'reporter@example.com', 'message': REPORT_TEXT, '_save': 'Save'},
        )
        entry = LogEntry.objects.get()

        urls = (
            reverse('admin:admin_logentry_changelist'),
            reverse('admin:admin_logentry_change', args=[entry.pk]),
            reverse('admin:admin_logentry_history', args=[entry.pk]),
            reverse('admin:harassment_harassment_history', args=[report.pk]),
            reverse('admin:index'),
        )

        for url in urls:
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200, url)
            self.assertNotContains(response, REPORT_TEXT, msg_prefix=url)

    def test_admin_success_message_does_not_carry_the_report(self):
        """The messages framework renders str(obj) and stores it in the session."""
        report = self.create_report()

        response = self.client.post(
            reverse('admin:harassment_harassment_change', args=[report.pk]),
            {'email': 'reporter@example.com', 'message': REPORT_TEXT, '_save': 'Save'},
        )
        self.assertEqual(response.status_code, 302)

        stored = ' '.join(str(message) for message in get_messages(response.wsgi_request))
        self.assertIn(f'#{report.pk}', stored)
        self.assertNotIn(REPORT_TEXT, stored)

    def test_log_viewer_without_report_permission_only_sees_the_label(self):
        report = self.create_report()
        self.client.post(
            reverse('admin:harassment_harassment_change', args=[report.pk]),
            {'email': 'reporter@example.com', 'message': REPORT_TEXT, '_save': 'Save'},
        )

        self.client.force_login(self.create_log_viewer(), backend='members.backends.AuthBackend')

        response = self.client.get(reverse('admin:admin_logentry_changelist'))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, REPORT_TEXT)
        self.assertContains(response, f'#{report.pk}')

        denied = self.client.get(reverse('admin:harassment_harassment_changelist'))
        self.assertEqual(denied.status_code, 403)

    def test_triage_snapshot_does_not_print_report_text(self):
        """incident_check prints the admin log, so the stored label is what it shows."""
        report = self.create_report()
        self.client.post(
            reverse('admin:harassment_harassment_change', args=[report.pk]),
            {'email': 'reporter@example.com', 'message': REPORT_TEXT, '_save': 'Save'},
        )

        output = StringIO()
        call_command('incident_check', '--limit', '5', stdout=output)

        self.assertIn(f'Trakasserianmälan #{report.pk}', output.getvalue())
        self.assertNotIn(REPORT_TEXT, output.getvalue())

    def create_log_viewer(self):
        """A staff member who may read the log but not the reports themselves."""
        group = Group.objects.create(name=settings.STAFF_GROUPS[0])
        group.permissions.add(
            Permission.objects.get(
                content_type=ContentType.objects.get_for_model(LogEntry),
                codename='view_logentry',
            )
        )
        viewer = get_user_model().objects.create_user(
            username='harassmentlogviewer',
            email='harassmentlogviewer@example.com',
            password='pass',
        )
        viewer.groups.add(group)
        return viewer


class HarassmentAdminLogMigrationTests(TestCase):
    """Historical log rows written before the model stopped leaking are redacted."""

    migration = importlib.import_module('harassment.migrations.0002_redact_admin_log_reports')

    @classmethod
    def setUpTestData(cls):
        cls.admin_user = get_user_model().objects.create_superuser(
            username='harassmentmigrationadmin',
            email='harassmentmigrationadmin@example.com',
            password='pass',
        )

    def create_log_entry(self, content_type, object_id):
        return LogEntry.objects.create(
            user=self.admin_user,
            action_time=timezone.now(),
            content_type=content_type,
            object_id=object_id,
            object_repr=REPORT_TEXT,
            action_flag=ADDITION,
            change_message='[]',
        )

    def redact(self):
        self.migration.redact_report_log_entries(apps, None)

    def test_historical_entries_are_redacted_for_current_and_legacy_app_labels(self):
        report = Harassment.objects.create(email='reporter@example.com', message=REPORT_TEXT)
        current = self.create_log_entry(ContentType.objects.get_for_model(Harassment), str(report.pk))
        legacy_type, _ = ContentType.objects.get_or_create(app_label='social', model='harassment')
        legacy = self.create_log_entry(legacy_type, '7')

        self.redact()

        for entry in (current, legacy):
            entry.refresh_from_db()
            self.assertNotIn(REPORT_TEXT, entry.object_repr)
            self.assertEqual(entry.object_repr, f'Trakasserianmälan #{entry.object_id}')

    def test_redaction_keeps_the_report_id_and_the_change_message(self):
        report = Harassment.objects.create(email='reporter@example.com', message=REPORT_TEXT)
        entry = self.create_log_entry(ContentType.objects.get_for_model(Harassment), str(report.pk))

        self.redact()
        self.redact()

        entry.refresh_from_db()
        self.assertEqual(entry.object_repr, f'Trakasserianmälan #{report.pk}')
        self.assertEqual(entry.change_message, '[]')


class HarassmentAdminLogRedactionCommandTests(TestCase):
    """A pod running the older image can still write text after the migration."""

    @classmethod
    def setUpTestData(cls):
        cls.admin_user = get_user_model().objects.create_superuser(
            username='harassmentcommandadmin',
            email='harassmentcommandadmin@example.com',
            password='pass',
        )

    def create_log_entry(self, content_type, object_id, object_repr):
        return LogEntry.objects.create(
            user=self.admin_user,
            action_time=timezone.now(),
            content_type=content_type,
            object_id=object_id,
            object_repr=object_repr,
            action_flag=ADDITION,
            change_message='[]',
        )

    def redact(self):
        output = StringIO()
        call_command('redact_harassment_logs', stdout=output)
        return output.getvalue()

    def test_command_redacts_stored_report_text_for_both_app_labels(self):
        report = Harassment.objects.create(email='reporter@example.com', message=REPORT_TEXT)
        current = self.create_log_entry(ContentType.objects.get_for_model(Harassment), str(report.pk), REPORT_TEXT)
        legacy_type, _ = ContentType.objects.get_or_create(app_label='social', model='harassment')
        legacy = self.create_log_entry(legacy_type, '7', REPORT_TEXT)

        output = self.redact()

        self.assertIn('Redacted 2 admin log entries', output)
        for entry in (current, legacy):
            entry.refresh_from_db()
            self.assertEqual(entry.object_repr, f'Trakasserianmälan #{entry.object_id}')

    def test_command_is_idempotent_and_leaves_other_entries_alone(self):
        report = Harassment.objects.create(email='reporter@example.com', message=REPORT_TEXT)
        entry = self.create_log_entry(ContentType.objects.get_for_model(Harassment), str(report.pk), REPORT_TEXT)
        other = self.create_log_entry(
            ContentType.objects.get_for_model(HarassmentEmailRecipient), '3', 'recipient@example.com'
        )

        self.redact()
        second_run = self.redact()

        entry.refresh_from_db()
        other.refresh_from_db()
        self.assertEqual(entry.object_repr, f'Trakasserianmälan #{report.pk}')
        self.assertEqual(other.object_repr, 'recipient@example.com')
        self.assertIn('Redacted 0 admin log entries', second_run)
