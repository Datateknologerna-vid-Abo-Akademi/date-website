from unittest.mock import patch

from django.http import HttpResponse
from django.test import SimpleTestCase
from django.test.client import RequestFactory

from core.urls import helpers


class UrlHelpersTests(SimpleTestCase):
    def setUp(self):
        self.request_factory = RequestFactory()

    def test_app_enabled_matches_plain_and_dotted_names(self):
        with patch.object(helpers.settings, "INSTALLED_APPS", ["members", "archive.apps.ArchiveConfig"]):
            self.assertTrue(helpers.app_enabled("members"))
            self.assertTrue(helpers.app_enabled("archive"))
            self.assertFalse(helpers.app_enabled("news"))

    def test_optional_include_returns_empty_when_app_disabled(self):
        with patch.object(helpers.settings, "INSTALLED_APPS", ["members"]):
            self.assertEqual(helpers.optional_include("news/", "news.urls", "news"), [])

    def test_optional_include_returns_route_when_app_enabled(self):
        with patch.object(helpers.settings, "INSTALLED_APPS", ["news"]):
            patterns = helpers.optional_include("news/", "news.urls", "news")
        self.assertEqual(len(patterns), 1)
        self.assertEqual(str(patterns[0].pattern), "news/")

    def test_optional_members_includes_without_auth_urls(self):
        with patch.object(helpers.settings, "INSTALLED_APPS", ["members"]):
            patterns = helpers.optional_members_includes(prefix="users/", include_auth_urls=False)
        self.assertEqual(len(patterns), 1)
        self.assertEqual(str(patterns[0].pattern), "users/")

    def test_optional_members_includes_with_auth_urls(self):
        with patch.object(helpers.settings, "INSTALLED_APPS", ["members"]):
            patterns = helpers.optional_members_includes(prefix="members/", include_auth_urls=True)
        self.assertEqual(len(patterns), 2)
        self.assertEqual(str(patterns[0].pattern), "members/")
        self.assertEqual(str(patterns[1].pattern), "members/")

    def test_optional_include_returns_empty_when_legacy_routes_disabled(self):
        with patch.object(helpers.settings, "LEGACY_TEMPLATE_ROUTES_ENABLED", False):
            patterns = helpers.optional_include("news/", "news.urls", "news")
        self.assertEqual(patterns, [])

    def test_optional_members_includes_returns_empty_when_legacy_routes_disabled(self):
        with patch.object(helpers.settings, "LEGACY_TEMPLATE_ROUTES_ENABLED", False):
            patterns = helpers.optional_members_includes(prefix="members/", include_auth_urls=True)
        self.assertEqual(patterns, [])

    def test_legacy_index_returns_original_view_when_legacy_routes_enabled(self):
        def sample_view(_request):
            return HttpResponse("legacy")

        with patch.object(helpers.settings, "LEGACY_TEMPLATE_ROUTES_ENABLED", True):
            view = helpers.legacy_index(sample_view)
            response = view(self.request_factory.get("/"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b"legacy")

    def test_legacy_index_redirects_when_legacy_routes_disabled(self):
        def sample_view(_request):
            return HttpResponse("legacy")

        with patch.object(helpers.settings, "LEGACY_TEMPLATE_ROUTES_ENABLED", False), patch.object(
            helpers.settings, "FRONTEND_DEFAULT_ROUTE", "/events"
        ):
            view = helpers.legacy_index(sample_view)
            response = view(self.request_factory.get("/"))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers.get("Location"), "/events")
