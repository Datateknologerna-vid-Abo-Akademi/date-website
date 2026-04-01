from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.contrib.admin.models import LogEntry, ADDITION
from django.conf import settings
from django.core.cache import cache
from django.utils import translation

from date.views import handler500


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

    def test_admin_respects_english_language_cookie(self):
        self.client.login(username="admin", password="pass")
        self.client.cookies[settings.LANGUAGE_COOKIE_NAME] = "en"
        response = self.client.get(reverse("admin:admin_logentry_changelist"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.wsgi_request.LANGUAGE_CODE, "en")


class LanguageSelectionTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        cache.clear()

    def test_set_language_persists_cookie(self):
        response = self.client.post(
            reverse("set_lang"),
            {"lang": "fi"},
            HTTP_REFERER=reverse("index"),
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.cookies[settings.LANGUAGE_COOKIE_NAME].value, "fi")
        self.assertEqual(response["Location"], reverse("index"))

    def test_set_language_falls_back_to_homepage_without_referer(self):
        response = self.client.post(
            reverse("set_lang"),
            {"lang": "sv"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], reverse("index"))
        self.assertEqual(response.cookies[settings.LANGUAGE_COOKIE_NAME].value, "sv")

    def test_homepage_renders_language_switcher_in_english(self):
        self.client.cookies[settings.LANGUAGE_COOKIE_NAME] = "en"
        response = self.client.get(reverse("index"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.wsgi_request.LANGUAGE_CODE, "en")
        self.assertContains(response, "Language")

    def test_homepage_renders_language_switcher_in_finnish(self):
        self.client.cookies[settings.LANGUAGE_COOKIE_NAME] = "fi"
        response = self.client.get(reverse("index"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.wsgi_request.LANGUAGE_CODE, "fi")
        self.assertContains(response, "Kieli")

    def test_homepage_preserves_swedish_shared_labels_and_fixed_terms(self):
        self.client.cookies[settings.LANGUAGE_COOKIE_NAME] = "sv"
        response = self.client.get(reverse("index"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.wsgi_request.LANGUAGE_CODE, "sv")
        self.assertContains(response, "Språk")
        self.assertContains(response, "Adress")
        self.assertContains(response, "Joke")

    def test_404_page_renders_in_selected_english_language(self):
        self.client.cookies[settings.LANGUAGE_COOKIE_NAME] = "en"
        response = self.client.get("/this-page-does-not-exist/")
        self.assertEqual(response.status_code, 404)
        self.assertContains(response, "Page not found", status_code=404)

    def test_404_page_renders_in_selected_swedish_language(self):
        self.client.cookies[settings.LANGUAGE_COOKIE_NAME] = "sv"
        response = self.client.get("/this-page-does-not-exist/")
        self.assertEqual(response.status_code, 404)
        self.assertContains(response, "Sidan hittades inte", status_code=404)

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
            reverse("set_lang"),
            {"lang": "en"},
            HTTP_REFERER=reverse("index"),
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.cookies[settings.LANGUAGE_COOKIE_NAME].value, "sv")

    @override_settings(
        ENABLE_LANGUAGE_FEATURES=False,
        LANGUAGES=(("sv", "Svenska"),),
    )
    def test_homepage_hides_language_switcher_when_language_features_disabled(self):
        self.client.cookies[settings.LANGUAGE_COOKIE_NAME] = "en"
        response = self.client.get(reverse("index"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.wsgi_request.LANGUAGE_CODE, "sv")
        self.assertNotContains(response, 'action="/set_lang/"')
        self.assertNotContains(response, 'name="lang"')
