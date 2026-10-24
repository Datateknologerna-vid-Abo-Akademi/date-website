"""Focused tests for the admin content and per-request caching changes.

These pin the behavior the admin performance pass introduced: the publications
inline joins the collection its public link reads, gallery previews load lazily,
the singleton settings admins ask the database once per request, and the news
changelist skips the full result count.
"""

from types import SimpleNamespace

from django.contrib import admin
from django.db import connection
from django.test import RequestFactory, TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from booking.admin import BookingSettingsAdmin
from booking.models import BookingSettings
from feedback.admin import FeedbackFormSettingsAdmin
from feedback.models import FeedbackFormSettings
from gallery.admin import safe_image_preview
from members.models import Member
from news.admin import PostAdmin
from news.models import Post
from publications.admin import PublicationInline
from publications.models import PDFFile, PublicationCollection


class AdminUserTestCase(TestCase):
    def setUp(self):
        self.admin_user = Member.objects.create_superuser(
            username="perf-content-admin",
            password="pass",
            email="perf-content-admin@example.com",
        )
        self.client.force_login(self.admin_user)


class PublicationInlineQueryTests(AdminUserTestCase):
    def setUp(self):
        super().setUp()
        self.collection = PublicationCollection.objects.create(
            title="Performance collection",
            slug="performance-collection",
        )
        self._create_publications(0, 5)
        self.request = RequestFactory().get(
            reverse("admin:publications_publicationcollection_change", args=[self.collection.pk])
        )
        self.request.user = self.admin_user
        self.inline = PublicationInline(PDFFile, admin.site)

    def _create_publications(self, start, count):
        for index in range(start, start + count):
            PDFFile.objects.create(
                collection=self.collection,
                title=f"Performance publication {index}",
                slug=f"performance-publication-{index}",
            )

    def test_get_queryset_selects_the_collection(self):
        queryset = self.inline.get_queryset(self.request)

        self.assertIn("collection", queryset.query.select_related)

    def test_collection_change_page_does_not_query_per_publication(self):
        url = reverse("admin:publications_publicationcollection_change", args=[self.collection.pk])
        with CaptureQueriesContext(connection) as baseline:
            response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        self._create_publications(5, 20)

        with CaptureQueriesContext(connection) as full:
            response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertLessEqual(len(full.captured_queries) - len(baseline.captured_queries), 3)


class GalleryPreviewTests(TestCase):
    def test_preview_is_lazy_and_decodes_async(self):
        preview = str(
            safe_image_preview(
                SimpleNamespace(url="/media/gallery/photo.jpg", name="gallery/photo.jpg"),
            )
        )

        self.assertIn('src="/media/gallery/photo.jpg"', preview)
        self.assertIn('loading="lazy"', preview)
        self.assertIn('decoding="async"', preview)


class SingletonPermissionQueryTests(AdminUserTestCase):
    def test_feedback_settings_queries_once_per_request(self):
        FeedbackFormSettings.objects.all().delete()
        FeedbackFormSettings.objects.create(pk=5, intro_text="Performance")
        request = RequestFactory().get("/admin/feedback/feedbackformsettings/")
        request.user = self.admin_user
        model_admin = FeedbackFormSettingsAdmin(FeedbackFormSettings, admin.site)

        with CaptureQueriesContext(connection) as queries:
            first = model_admin.has_add_permission(request)
            second = model_admin.has_add_permission(request)

        self.assertFalse(first)
        self.assertFalse(second)
        self.assertEqual(len(queries.captured_queries), 1)

    def test_booking_settings_queries_once_per_request(self):
        BookingSettings.get_solo()
        request = RequestFactory().get("/admin/booking/bookingsettings/")
        request.user = self.admin_user
        model_admin = BookingSettingsAdmin(BookingSettings, admin.site)

        with CaptureQueriesContext(connection) as queries:
            first = model_admin.has_add_permission(request)
            second = model_admin.has_add_permission(request)

        self.assertFalse(first)
        self.assertFalse(second)
        self.assertEqual(len(queries.captured_queries), 1)


class NewsAdminPerformanceTests(TestCase):
    def test_post_changelist_skips_the_full_result_count(self):
        model_admin = admin.site._registry[Post]

        self.assertIsInstance(model_admin, PostAdmin)
        self.assertFalse(model_admin.show_full_result_count)
