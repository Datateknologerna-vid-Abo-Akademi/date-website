from unittest.mock import patch

from django.test import SimpleTestCase

from core.urls import helpers


class UrlHelpersTests(SimpleTestCase):
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
