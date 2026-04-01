from datetime import date
from unittest.mock import patch

from django.test import TestCase
from django.test.utils import override_settings
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.contrib.admin.models import LogEntry, ADDITION

from date.views import get_homepage_template_name


class AuditLogTestCase(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_superuser(
            username="admin",
            password="pass",
            email="admin@example.com",
        )
        ct = ContentType.objects.get_for_model(get_user_model())
        LogEntry.objects.log_action(
            user_id=self.user.pk,
            content_type_id=ct.pk,
            object_id=self.user.pk,
            object_repr=str(self.user),
            action_flag=ADDITION,
            change_message="created user",
        )

    def test_audit_log_accessible(self):
        self.client.login(username="admin", password="pass")
        url = reverse("admin:admin_logentry_changelist")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "created user")


class HomepageTemplateSelectionTests(TestCase):
    @override_settings(PROJECT_NAME='kk')
    @patch('date.views.timezone.localdate', return_value=date(2026, 4, 1))
    @patch('date.views.random.randrange', return_value=0)
    def test_kk_uses_april_template_on_april_first_when_roll_matches(self, _randrange, _localdate):
        self.assertEqual(get_homepage_template_name(), 'date/april_start.html')

    @override_settings(PROJECT_NAME='kk')
    @patch('date.views.timezone.localdate', return_value=date(2026, 4, 1))
    @patch('date.views.random.randrange', return_value=1)
    def test_kk_uses_regular_template_on_april_first_when_roll_misses(self, _randrange, _localdate):
        self.assertEqual(get_homepage_template_name(), 'date/start.html')

    @override_settings(PROJECT_NAME='kk')
    @patch('date.views.timezone.localdate', return_value=date(2026, 4, 2))
    def test_kk_uses_regular_template_outside_april_first(self, _localdate):
        self.assertEqual(get_homepage_template_name(), 'date/start.html')

    @override_settings(PROJECT_NAME='date')
    @patch('date.views.timezone.localdate', return_value=date(2026, 4, 1))
    @patch('date.views.random.randrange', return_value=0)
    def test_non_kk_never_uses_april_template(self, _randrange, _localdate):
        self.assertEqual(get_homepage_template_name(), 'date/start.html')
