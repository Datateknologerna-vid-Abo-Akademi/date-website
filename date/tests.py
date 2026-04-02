from datetime import date
from unittest.mock import patch

from django.conf import settings
from django.contrib.admin.models import ADDITION, LogEntry
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.core.cache import cache
from django.test import RequestFactory, TestCase
from django.test.utils import override_settings
from django.urls import reverse
from django.utils import translation

from date.language_utils import localize_url, strip_language_prefix
from date.views import get_homepage_template_name, handler500


<<<<<<< HEAD
def localized_reverse(name, language_code, **kwargs):
    with translation.override(language_code):
        return reverse(name, **kwargs)
=======
def localized_reverse(name, language_code, *args, **kwargs):
    with translation.override(language_code):
        return reverse(name, args=args or None, kwargs=kwargs or None)
>>>>>>> develop


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

    def test_admin_respects_english_language_path(self):
        self.client.login(username="admin", password="pass")
        response = self.client.get(localized_reverse("admin:admin_logentry_changelist", "en"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.wsgi_request.LANGUAGE_CODE, "en")

    def test_admin_shows_language_switcher_when_enabled(self):
        self.client.login(username="admin", password="pass")
<<<<<<< HEAD
        response = self.client.get(localized_reverse("admin:admin_logentry_changelist", "en"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="admin-language-switcher"')
        self.assertContains(response, f'action="{localized_reverse("set_lang", "en")}"')
=======
        self.client.cookies[settings.LANGUAGE_COOKIE_NAME] = "en"
        response = self.client.get(reverse("admin:admin_logentry_changelist"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="admin-language-switcher"')
        self.assertContains(response, f'action="{reverse("set_lang")}"')
>>>>>>> develop

    @override_settings(
        ENABLE_LANGUAGE_FEATURES=False,
        LANGUAGES=(("sv", "Svenska"),),
    )
    def test_admin_hides_language_switcher_when_disabled(self):
        self.client.login(username="admin", password="pass")
        response = self.client.get(reverse("admin:admin_logentry_changelist"))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'id="admin-language-switcher"')


class StripLanguagePrefixTests(TestCase):
    def test_strips_english_prefix(self):
        self.assertEqual(strip_language_prefix("/en/news/"), "/news/")

    def test_strips_finnish_prefix(self):
        self.assertEqual(strip_language_prefix("/fi/events/"), "/events/")

    def test_strips_swedish_prefix(self):
        self.assertEqual(strip_language_prefix("/sv/about/"), "/about/")

    def test_language_only_root_becomes_slash(self):
        self.assertEqual(strip_language_prefix("/en/"), "/")

    def test_no_prefix_unchanged(self):
        self.assertEqual(strip_language_prefix("/news/"), "/news/")

    def test_root_unchanged(self):
        self.assertEqual(strip_language_prefix("/"), "/")

    def test_empty_returns_empty(self):
        self.assertEqual(strip_language_prefix(""), "")

    def test_none_returns_none(self):
        self.assertIsNone(strip_language_prefix(None))

    def test_absolute_url_unchanged(self):
        self.assertEqual(strip_language_prefix("https://example.com/en/news/"), "https://example.com/en/news/")

    def test_anchor_unchanged(self):
        self.assertEqual(strip_language_prefix("#section"), "#section")

    def test_mailto_unchanged(self):
        self.assertEqual(strip_language_prefix("mailto:foo@example.com"), "mailto:foo@example.com")

    def test_tel_unchanged(self):
        self.assertEqual(strip_language_prefix("tel:+358501234567"), "tel:+358501234567")

    def test_relative_url_normalized(self):
        self.assertEqual(strip_language_prefix("en/news/"), "/news/")


class LocalizeUrlTests(TestCase):
    def test_strips_english_prefix(self):
        self.assertEqual(localize_url("/en/news/", "en"), "/news/")

    def test_strips_finnish_prefix(self):
        self.assertEqual(localize_url("/fi/news/", "fi"), "/news/")

    def test_bare_url_unchanged(self):
        self.assertEqual(localize_url("/news/", "sv"), "/news/")

    def test_strips_prefix_regardless_of_target_language(self):
        self.assertEqual(localize_url("/en/events/", "sv"), "/events/")
        self.assertEqual(localize_url("/fi/events/", "en"), "/events/")

    def test_absolute_url_unchanged(self):
        self.assertEqual(localize_url("https://example.com/en/news/", "sv"), "https://example.com/en/news/")

    def test_none_returns_none(self):
        self.assertIsNone(localize_url(None, "sv"))


class LanguageSelectionTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        cache.clear()

    def test_set_language_persists_cookie(self):
        response = self.client.post(
            localized_reverse("set_lang", "sv"),
            {"lang": "fi"},
            HTTP_REFERER=localized_reverse("index", "sv"),
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.cookies[settings.LANGUAGE_COOKIE_NAME].value, "fi")
<<<<<<< HEAD
        self.assertEqual(response["Location"], localized_reverse("index", "fi"))
=======
        self.assertEqual(response["Location"], "/")

    def test_set_language_strips_legacy_prefixed_referer(self):
        response = self.client.post(
            reverse("set_lang"),
            {"lang": "fi"},
            HTTP_REFERER="/en/news/",
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "/news/")
        self.assertEqual(response.cookies[settings.LANGUAGE_COOKIE_NAME].value, "fi")

    def test_set_language_redirects_to_same_path_when_switching_language(self):
        response = self.client.post(
            reverse("set_lang"),
            {"lang": "en"},
            HTTP_REFERER="/news/",
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "/news/")
        self.assertEqual(response.cookies[settings.LANGUAGE_COOKIE_NAME].value, "en")

    def test_set_language_preserves_query_string(self):
        response = self.client.post(
            reverse("set_lang"),
            {"lang": "fi"},
            HTTP_REFERER="/news/?page=2",
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "/news/?page=2")
>>>>>>> develop

    def test_set_language_falls_back_to_homepage_without_referer(self):
        response = self.client.post(
            localized_reverse("set_lang", "sv"),
            {"lang": "sv"},
        )
        self.assertEqual(response.status_code, 302)
<<<<<<< HEAD
        self.assertEqual(response["Location"], localized_reverse("index", "sv"))
        self.assertEqual(response.cookies[settings.LANGUAGE_COOKIE_NAME].value, "sv")

    def test_homepage_renders_language_switcher_in_english_path(self):
        response = self.client.get(localized_reverse("index", "en"))
=======
        self.assertEqual(response["Location"], "/")
        self.assertEqual(response.cookies[settings.LANGUAGE_COOKIE_NAME].value, "sv")

    def test_homepage_uses_cookie_language_on_non_prefixed_url(self):
        self.client.cookies[settings.LANGUAGE_COOKIE_NAME] = "en"
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.wsgi_request.LANGUAGE_CODE, "en")

    def test_homepage_uses_finnish_cookie_on_non_prefixed_url(self):
        self.client.cookies[settings.LANGUAGE_COOKIE_NAME] = "fi"
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.wsgi_request.LANGUAGE_CODE, "fi")

    def test_homepage_defaults_to_swedish_without_cookie_or_header(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.wsgi_request.LANGUAGE_CODE, settings.LANGUAGE_CODE)

    def test_accept_language_header_sets_language_on_non_prefixed_url(self):
        response = self.client.get("/", HTTP_ACCEPT_LANGUAGE="en")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.wsgi_request.LANGUAGE_CODE, "en")

    def test_cookie_takes_precedence_over_accept_language_header(self):
        self.client.cookies[settings.LANGUAGE_COOKIE_NAME] = "fi"
        response = self.client.get("/", HTTP_ACCEPT_LANGUAGE="en")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.wsgi_request.LANGUAGE_CODE, "fi")

    def test_404_page_renders_in_finnish_via_accept_language(self):
        response = self.client.get("/this-page-does-not-exist/", HTTP_ACCEPT_LANGUAGE="fi")
        self.assertEqual(response.status_code, 404)
        self.assertContains(response, "Sivua ei löydetty", status_code=404)

    def test_homepage_renders_language_switcher_in_english_via_cookie(self):
        self.client.cookies[settings.LANGUAGE_COOKIE_NAME] = "en"
        response = self.client.get("/")
>>>>>>> develop
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.wsgi_request.LANGUAGE_CODE, "en")
        self.assertContains(response, "Language")

<<<<<<< HEAD
    def test_homepage_renders_language_switcher_in_finnish_path(self):
        response = self.client.get(localized_reverse("index", "fi"))
=======
    def test_homepage_renders_language_switcher_in_finnish_via_cookie(self):
        self.client.cookies[settings.LANGUAGE_COOKIE_NAME] = "fi"
        response = self.client.get("/")
>>>>>>> develop
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.wsgi_request.LANGUAGE_CODE, "fi")
        self.assertContains(response, "Kieli")

<<<<<<< HEAD
    def test_homepage_preserves_swedish_shared_labels_and_fixed_terms_on_swedish_path(self):
        response = self.client.get(localized_reverse("index", "sv"))
=======
    def test_homepage_preserves_swedish_labels_by_default(self):
        response = self.client.get("/")
>>>>>>> develop
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.wsgi_request.LANGUAGE_CODE, "sv")
        self.assertContains(response, "Språk")
        self.assertContains(response, "Adress")
        self.assertContains(response, "Joke")

<<<<<<< HEAD
    def test_404_page_renders_in_selected_english_language_path(self):
        response = self.client.get("/en/this-page-does-not-exist/")
        self.assertEqual(response.status_code, 404)
        self.assertContains(response, "Page not found", status_code=404)

    def test_404_page_renders_in_selected_swedish_language_path(self):
        response = self.client.get("/sv/this-page-does-not-exist/")
        self.assertEqual(response.status_code, 404)
        self.assertContains(response, "Sidan hittades inte", status_code=404)

    def test_path_language_takes_precedence_over_cookie(self):
        self.client.cookies[settings.LANGUAGE_COOKIE_NAME] = "fi"
        response = self.client.get(localized_reverse("index", "en"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.wsgi_request.LANGUAGE_CODE, "en")
        self.assertContains(response, "Language")
=======
    def test_404_page_renders_in_english_via_accept_language(self):
        response = self.client.get("/this-page-does-not-exist/", HTTP_ACCEPT_LANGUAGE="en")
        self.assertEqual(response.status_code, 404)
        self.assertContains(response, "Page not found", status_code=404)

    def test_404_page_renders_in_swedish_by_default(self):
        response = self.client.get("/this-page-does-not-exist/")
        self.assertEqual(response.status_code, 404)
        self.assertContains(response, "Sidan hittades inte", status_code=404)

    def test_request_language_does_not_leak_after_response(self):
        with translation.override("sv"):
            self.client.cookies[settings.LANGUAGE_COOKIE_NAME] = "fi"
            response = self.client.get("/")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.wsgi_request.LANGUAGE_CODE, "fi")
            self.assertEqual(translation.get_language(), "sv")
>>>>>>> develop

    def test_500_page_renders_in_selected_swedish_language(self):
        request = self.factory.get("/")
        with translation.override("sv"):
            response = handler500(request)
        self.assertEqual(response.status_code, 500)
        self.assertContains(response, "Serverfel", status_code=500)

    @override_settings(
        ENABLE_LANGUAGE_FEATURES=False,
        LANGUAGES=(("sv", "Svenska"),),
    )
    def test_set_language_falls_back_to_default_when_language_features_disabled(self):
        response = self.client.post(
            localized_reverse("set_lang", "sv"),
            {"lang": "en"},
            HTTP_REFERER=localized_reverse("index", "sv"),
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.cookies[settings.LANGUAGE_COOKIE_NAME].value, "sv")

    @override_settings(
        ENABLE_LANGUAGE_FEATURES=False,
        LANGUAGES=(("sv", "Svenska"),),
    )
    def test_homepage_hides_language_switcher_when_language_features_disabled(self):
        self.client.cookies[settings.LANGUAGE_COOKIE_NAME] = "en"
<<<<<<< HEAD
        response = self.client.get(localized_reverse("index", "sv"))
=======
        response = self.client.get("/")
>>>>>>> develop
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.wsgi_request.LANGUAGE_CODE, "sv")
        self.assertNotContains(response, 'action="')
        self.assertNotContains(response, 'name="lang"')


class HomepageTemplateSelectionTests(TestCase):
    @override_settings(PROJECT_NAME="kk")
    @patch("date.views.timezone.localdate", return_value=date(2026, 4, 1))
    @patch("date.views.random.randrange", return_value=0)
    def test_kk_uses_april_template_on_april_first_when_roll_matches(self, _randrange, _localdate):
        self.assertEqual(get_homepage_template_name(), "date/april_start.html")

    @override_settings(PROJECT_NAME="kk")
    @patch("date.views.timezone.localdate", return_value=date(2026, 4, 1))
    @patch("date.views.random.randrange", return_value=1)
    def test_kk_uses_regular_template_on_april_first_when_roll_misses(self, _randrange, _localdate):
        self.assertEqual(get_homepage_template_name(), "date/start.html")

    @override_settings(PROJECT_NAME="kk")
    @patch("date.views.timezone.localdate", return_value=date(2026, 4, 2))
    def test_kk_uses_regular_template_outside_april_first(self, _localdate):
        self.assertEqual(get_homepage_template_name(), "date/start.html")

    @override_settings(PROJECT_NAME="date")
    @patch("date.views.timezone.localdate", return_value=date(2026, 4, 1))
    @patch("date.views.random.randrange", return_value=0)
    def test_non_kk_never_uses_april_template(self, _randrange, _localdate):
        self.assertEqual(get_homepage_template_name(), "date/start.html")
