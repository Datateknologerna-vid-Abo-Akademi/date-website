from datetime import date, timedelta
from unittest.mock import patch

from django.conf import settings
from django.contrib.admin.models import ADDITION, LogEntry
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.core.cache import cache
from django.template import Context, Template
from django.test import RequestFactory, TestCase
from django.test.utils import override_settings
from django.urls import reverse
from django.utils import timezone
from django.utils import translation

from date.views import get_homepage_template_name, handler500


def localized_reverse(name, language_code, *args, **kwargs):
    with translation.override(language_code):
        return reverse(name, args=args or None, kwargs=kwargs or None)


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
        response = self.client.get(localized_reverse("admin:admin_logentry_changelist", "en"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="admin-language-switcher"')
        self.assertContains(response, f'action="{localized_reverse("set_lang", "en")}"')

    @override_settings(
        ENABLE_LANGUAGE_FEATURES=False,
        LANGUAGES=(("sv", "Svenska"),),
    )
    def test_admin_hides_language_switcher_when_disabled(self):
        self.client.login(username="admin", password="pass")
        response = self.client.get(reverse("admin:admin_logentry_changelist"))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'id="admin-language-switcher"')


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
        self.assertEqual(response["Location"], localized_reverse("index", "fi"))

    def test_set_language_falls_back_to_homepage_without_referer(self):
        response = self.client.post(
            localized_reverse("set_lang", "sv"),
            {"lang": "sv"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], localized_reverse("index", "sv"))
        self.assertEqual(response.cookies[settings.LANGUAGE_COOKIE_NAME].value, "sv")

    def test_homepage_renders_language_switcher_in_english_path(self):
        response = self.client.get(localized_reverse("index", "en"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.wsgi_request.LANGUAGE_CODE, "en")
        self.assertContains(response, "Language")

    def test_homepage_renders_language_switcher_in_finnish_path(self):
        response = self.client.get(localized_reverse("index", "fi"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.wsgi_request.LANGUAGE_CODE, "fi")
        self.assertContains(response, "Kieli")

    def test_homepage_preserves_swedish_shared_labels_and_fixed_terms_on_swedish_path(self):
        response = self.client.get(localized_reverse("index", "sv"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.wsgi_request.LANGUAGE_CODE, "sv")
        self.assertContains(response, "Språk")
        self.assertContains(response, "Adress")
        self.assertContains(response, "Joke")

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

    def test_request_language_does_not_leak_after_response(self):
        with translation.override("sv"):
            response = self.client.get(localized_reverse("index", "fi"))
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.wsgi_request.LANGUAGE_CODE, "fi")
            self.assertEqual(translation.get_language(), "sv")

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
        response = self.client.get(localized_reverse("index", "sv"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.wsgi_request.LANGUAGE_CODE, "sv")
        self.assertNotContains(response, 'action="')
        self.assertNotContains(response, 'name="lang"')

    def test_localized_timeuntil_filter_uses_finnish_word_order(self):
        template = Template("{% load localized_time %}{{ value|localized_timeuntil }}")
        value = timezone.now() + timedelta(minutes=1)
        with translation.override("fi"):
            rendered = template.render(Context({"value": value}))
        self.assertTrue(rendered.endswith(" kuluttua"))
        self.assertIn("minuutin", rendered)

    def test_localized_timeuntil_filter_uses_finnish_genitive_for_zero_minutes(self):
        template = Template("{% load localized_time %}{{ value|localized_timeuntil }}")
        value = timezone.now() + timedelta(seconds=30)
        with translation.override("fi"):
            rendered = template.render(Context({"value": value}))
        self.assertEqual(rendered, "0 minuutin kuluttua")

    def test_localized_timeuntil_filter_uses_swedish_word_order(self):
        template = Template("{% load localized_time %}{{ value|localized_timeuntil }}")
        value = timezone.now() + timedelta(minutes=1)
        with translation.override("sv"):
            rendered = template.render(Context({"value": value}))
        self.assertTrue(rendered.startswith("om "))

    def test_localized_timesince_ago_filter_uses_finnish_word_order(self):
        template = Template("{% load localized_time %}{{ value|localized_timesince_ago }}")
        value = timezone.now() - timedelta(minutes=1)
        with translation.override("fi"):
            rendered = template.render(Context({"value": value}))
        self.assertTrue(rendered.endswith(" sitten"))

    def test_localized_timesince_ago_filter_uses_english_word_order(self):
        template = Template("{% load localized_time %}{{ value|localized_timesince_ago }}")
        value = timezone.now() - timedelta(minutes=1)
        with translation.override("en"):
            rendered = template.render(Context({"value": value}))
        self.assertTrue(rendered.endswith(" ago"))

    def test_localized_remaining_places_filter_uses_finnish_word_order(self):
        template = Template("{% load localized_time %}{{ value|localized_remaining_places }}")
        with translation.override("fi"):
            rendered = template.render(Context({"value": 80}))
        self.assertEqual(rendered, "80 paikkaa jäljellä!")

    def test_localized_remaining_places_filter_uses_swedish_word_order(self):
        template = Template("{% load localized_time %}{{ value|localized_remaining_places }}")
        with translation.override("sv"):
            rendered = template.render(Context({"value": 80}))
        self.assertEqual(rendered, "Det finns 80 platser!")


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
