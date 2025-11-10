from django.contrib.admin.models import ADDITION, LogEntry
from django.contrib.contenttypes.models import ContentType
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model

from core.cache_keys import DATE_INDEX_CACHE_KEY


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


class DateCacheTestCase(TestCase):
    def test_homepage_populates_cache(self):
        cache.delete(DATE_INDEX_CACHE_KEY)
        response = self.client.get(reverse('index'))
        self.assertEqual(response.status_code, 200)
        cached = cache.get(DATE_INDEX_CACHE_KEY)
        self.assertIsNotNone(cached)
        self.assertEqual(cached.status_code, response.status_code)
