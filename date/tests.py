import importlib
import re
import time
import unittest
from datetime import date, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from django.apps import apps
from django.conf import settings
from django.contrib import admin
from django.contrib.admin.models import ADDITION, LogEntry
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db import connection
from django.http import HttpResponse
from django.template import Context, Template
from django.template.loader import render_to_string
from django.test import RequestFactory, SimpleTestCase, TestCase
from django.test.utils import CaptureQueriesContext, override_settings
from django.urls import clear_url_caches, reverse, set_urlconf
from django.utils import timezone, translation

from ads.models import AdUrl
from core.admin import admin_site
from date.language_utils import localize_url, strip_language_prefix
from date.middleware import ConnectionLifecycleMiddleware
from date.templatetags.social_icons import social_icon_template
from date.views import (
    _homepage_context,
    _homepage_version_key,
    format_calendar_events,
    get_homepage_template_name,
    get_recent_albins_angels_post,
    handler404,
    handler500,
)
from events.models import Event
from instagram.models import IgUrl
from news.models import Category, Post

ASSOCIATION_SETTINGS_MODULES = {
    "date": "core.settings.date",
    "kk": "core.settings.kk",
    "biocum": "core.settings.biocum",
    "demo": "core.settings.demo",
    "pulterit": "core.settings.pulterit",
    "sf": "core.settings.sf",
    "impuls": "core.settings.impuls",
}

# The Font Awesome compatible build of Line Awesome. Shared templates use fa-* /
# fas / far classes, which the plain line-awesome build does not define.
FA_COMPATIBLE_ICON_CSS = (
    "https://cdnjs.cloudflare.com/ajax/libs/line-awesome/1.3.0/font-awesome-line-awesome/css/all.min.css"
)
FA_COMPATIBLE_ICON_CSS_SRI = "sha384-snzOGIbz+keYJBq8ozkYChzFE6HnRT5PIEwo25BGyLtpC4G3qF/YAP4vRkinYp7+"


def localized_reverse(name, language_code, *args, **kwargs):
    with translation.override(language_code):
        return reverse(name, args=args or None, kwargs=kwargs or None)


class SiteShellTemplateTests(TestCase):
    def _content_context(self):
        return {
            "ASSOCIATION_NAME": "Test Association",
            "ASSOCIATION_NAME_FULL": "Test Association rf",
            "ASSOCIATION_NAME_FULL_RF": "Test Association rf",
            "ASSOCIATION_NAME_SHORT": "TA",
            "ASSOCIATION_EMAIL": "test@example.com",
            "ASSOCIATION_ADDRESS_L1": "Line 1",
            "ASSOCIATION_ADDRESS_L2": "Line 2",
            "ASSOCIATION_POSTAL_CODE": "12345",
            "ASSOCIATION_OFFICE_HOURS": "",
            "SOCIAL_BUTTONS": [],
            "categories": [],
            "urls": [],
            "ENABLE_LANGUAGE_FEATURES": False,
            "LANGUAGES": (("sv", "Svenska"),),
        }

    def test_base_template_has_one_body_and_keeps_shell_sections(self):
        rendered = render_to_string("core/base.html", self._content_context())

        self.assertEqual(len(re.findall(r"<body\b", rendered)), 1)
        self.assertEqual(rendered.count("</body>"), 1)
        self.assertIn("<nav", rendered)
        self.assertIn("association-footer", rendered)
        self.assertIn("core/js/external-links.js", rendered)
        self.assertLess(rendered.index("<body>"), rendered.index("<nav"))
        self.assertLess(rendered.index("core/js/external-links.js"), rendered.index("</body>"))

    def test_base_template_loads_font_awesome_compatibility_css(self):
        rendered = render_to_string("core/base.html", self._content_context())
        self.assertIn(FA_COMPATIBLE_ICON_CSS, rendered)
        self.assertIn(FA_COMPATIBLE_ICON_CSS_SRI, rendered)

    def test_every_association_shell_loads_font_awesome_compatibility_css(self):
        # Each association resolves core/base.html through its own template dirs, so
        # rendering only under the default variant misses variant-level overrides of
        # the icon_head block. sf overrides it, and the plain Line Awesome build it
        # once pointed at does not define the fa-* classes the shared templates use.
        plain_line_awesome = "line-awesome/1.3.0/line-awesome/css/line-awesome.min.css"
        for association, settings_module in ASSOCIATION_SETTINGS_MODULES.items():
            with self.subTest(association=association):
                module = importlib.import_module(settings_module)
                with override_settings(PROJECT_NAME=association, TEMPLATES=module.TEMPLATES):
                    rendered = render_to_string("core/base.html", self._content_context())
                self.assertIn(FA_COMPATIBLE_ICON_CSS, rendered)
                self.assertIn(FA_COMPATIBLE_ICON_CSS_SRI, rendered)
                self.assertNotIn(plain_line_awesome, rendered)

    def test_header_uses_unique_dropdown_ids_for_categories(self):
        categories = [
            SimpleNamespace(category_name="About", use_category_url=False, url=""),
            SimpleNamespace(category_name="Members", use_category_url=False, url=""),
        ]
        template = Template("{% include 'core/header.html' %}")
        rendered = template.render(
            Context(
                {
                    **self._content_context(),
                    "categories": categories,
                }
            )
        )

        dropdown_ids = re.findall(r'id="(navbarDropdownMenuLink\d+)"', rendered)
        self.assertEqual(dropdown_ids, ["navbarDropdownMenuLink0", "navbarDropdownMenuLink1"])
        self.assertEqual(len(dropdown_ids), len(set(dropdown_ids)))
        self.assertIn('aria-labelledby="navbarDropdownMenuLink0"', rendered)
        self.assertIn('aria-labelledby="navbarDropdownMenuLink1"', rendered)
        self.assertNotIn('id="navbarDarkDropdownMenuLink"', rendered)

    def test_pulterit_header_override_keeps_custom_logo_and_container(self):
        pulterit_settings = importlib.import_module("core.settings.pulterit")

        with override_settings(
            TEMPLATES=pulterit_settings.TEMPLATES,
            STATICFILES_DIRS=pulterit_settings.STATICFILES_DIRS,
        ):
            template = Template("{% include 'core/header.html' %}")
            rendered = template.render(
                Context(
                    {
                        **self._content_context(),
                        "ASSOCIATION_NAME": "Pulterit",
                        "ENABLE_LANGUAGE_FEATURES": True,
                        "LANGUAGES": (("sv", "Svenska"), ("en", "English")),
                    }
                )
            )

        self.assertIn("container-fluid px-3", rendered)
        self.assertIn("pulterit-white-wo-text.svg", rendered)
        self.assertIn("languageDropdownMenuLink", rendered)

    def test_pulterit_base_loads_header_overrides_after_shared_header_css(self):
        pulterit_settings = importlib.import_module("core.settings.pulterit")

        with override_settings(
            TEMPLATES=pulterit_settings.TEMPLATES,
            STATICFILES_DIRS=pulterit_settings.STATICFILES_DIRS,
        ):
            rendered = render_to_string(
                "core/base.html",
                {
                    **self._content_context(),
                    "ASSOCIATION_NAME": "Pulterit",
                    "ENABLE_LANGUAGE_FEATURES": True,
                    "LANGUAGES": (("sv", "Svenska"), ("en", "English")),
                },
            )

        shared_header_css = "core/css/header.css"
        pulterit_header_css = "core/css/header-overrides.css"
        self.assertIn(shared_header_css, rendered)
        self.assertIn(pulterit_header_css, rendered)
        self.assertLess(rendered.index(shared_header_css), rendered.index(pulterit_header_css))

    def test_pulterit_footer_keeps_shared_and_association_classes_separate(self):
        pulterit_settings = importlib.import_module("core.settings.pulterit")

        with override_settings(
            TEMPLATES=pulterit_settings.TEMPLATES,
            STATICFILES_DIRS=pulterit_settings.STATICFILES_DIRS,
        ):
            template = Template("{% include 'core/footer.html' %}")
            rendered = template.render(Context(self._content_context()))

        self.assertIn('class="container association-footer pulterit-footer"', rendered)
        self.assertIn(
            'class="association-footer-shell pulterit-footer-shell"',
            rendered,
        )
        self.assertIn(
            "association-footer-content pulterit-footer-content",
            rendered,
        )
        self.assertIn("association-footer-brand pulterit-footer-brand", rendered)
        self.assertIn("association-footer-copy pulterit-footer-copy", rendered)
        self.assertNotIn("association-footerpulterit-footer", rendered)

    def test_impuls_partner_link_is_named_for_its_destination(self):
        impuls_settings = importlib.import_module("core.settings.impuls")
        rendered = {}

        with override_settings(
            TEMPLATES=impuls_settings.TEMPLATES,
            STATICFILES_DIRS=impuls_settings.STATICFILES_DIRS,
        ):
            for language in ("sv", "en"):
                with translation.override(language):
                    rendered[language] = render_to_string("core/footer.html", self._content_context())

        self.assertIn('aria-label="Åbo Akademi – psykologi"', rendered["sv"])
        self.assertIn('aria-label="Åbo Akademi University – Psychology"', rendered["en"])

        for language in ("sv", "en"):
            page = rendered[language]
            self.assertIn('href="https://www.abo.fi/utbildningsprogram/psykologi/"', page)
            self.assertIn('target="_blank"', page)
            self.assertIn('rel="noopener"', page)
            self.assertIn("<svg", page)
            self.assertIn("<path", page)

    def test_aa_partner_badge_only_renders_in_date_footer(self):
        # A fresh database seeds the category as "albins-angels", while
        # production uses the slug "aa". Creating it here with the seeded slug
        # proves the footer resolves the link through the category name.
        category = Category.objects.create(name="Albins Angels", slug="albins-angels")

        for association, settings_module in ASSOCIATION_SETTINGS_MODULES.items():
            with self.subTest(association=association):
                module = importlib.import_module(settings_module)
                with override_settings(TEMPLATES=module.TEMPLATES):
                    template = Template("{% include 'core/footer.html' %}")
                    rendered = template.render(Context(self._content_context()))
                if association == "date":
                    link = re.search(r'<a class="partner-link" href="([^"]*)"', rendered)
                    self.assertIsNotNone(link)
                    self.assertEqual(link.group(1), category.get_absolute_url())
                    self.assertEqual(rendered.count("date-footer-partner"), 1)
                    self.assertEqual(rendered.count("aa-logo-small.png"), 1)
                    badge = re.search(r"<img[^>]*aa-logo-small\.png[^>]*>", rendered)
                    self.assertIsNotNone(badge)
                    alt = re.search(r'alt="([^"]*)"', badge.group(0))
                    self.assertIsNotNone(alt)
                    self.assertTrue(alt.group(1).strip())
                else:
                    self.assertNotIn("aa-logo-small.png", rendered)

        # Impuls is checked separately: it layers the date templates but
        # overrides footer_right, and it is deliberately not part of
        # ASSOCIATION_SETTINGS_MODULES.
        impuls_settings = importlib.import_module("core.settings.impuls")
        with override_settings(TEMPLATES=impuls_settings.TEMPLATES):
            template = Template("{% include 'core/footer.html' %}")
            rendered = template.render(Context(self._content_context()))
        self.assertNotIn("aa-logo-small.png", rendered)

    def test_language_picker_hides_when_disabled_in_header_template(self):
        template = Template("{% include 'core/header.html' %}")
        rendered = template.render(Context(self._content_context()))

        self.assertNotIn('name="lang"', rendered)
        self.assertNotIn("language-dropdown-toggle", rendered)

    def test_footer_handles_blank_social_urls_and_office_hours(self):
        template = Template("{% include 'core/footer.html' %}")
        rendered = template.render(
            Context(
                {
                    **self._content_context(),
                    "SOCIAL_BUTTONS": [
                        ["fa-facebook-f", "https://example.com/facebook"],
                        ["fa-github", ""],
                    ],
                }
            )
        )

        self.assertIn("https://example.com/facebook", rendered)
        self.assertNotIn('href=""', rendered)
        self.assertIn("test@example.com", rendered)
        self.assertNotIn("test@example.com<br>", rendered)

    def test_footer_mixes_shared_svg_icons_with_icon_font_fallback(self):
        template = Template("{% include 'core/footer.html' %}")
        rendered = template.render(
            Context(
                {
                    **self._content_context(),
                    "SOCIAL_BUTTONS": [
                        ["fa-facebook-f", "https://example.com/facebook"],
                        ["tiktok", "https://example.com/tiktok"],
                        ["linktree", "https://example.com/linktree"],
                    ],
                }
            )
        )

        self.assertIn('<i class="fab fa-facebook-f"></i>', rendered)
        self.assertNotIn("fab tiktok", rendered)
        self.assertNotIn("fab linktree", rendered)
        self.assertEqual(rendered.count("<svg"), 2)
        self.assertIn('role="img" aria-label="TikTok"', rendered)
        self.assertIn('role="img" aria-label="Linktree"', rendered)
        self.assertNotIn('aria-label="Tiktok"', rendered)

    def test_footer_falls_back_to_the_icon_font_for_a_hostile_icon_name(self):
        hostile_name = "a" * 300
        template = Template("{% include 'core/footer.html' %}")
        rendered = template.render(
            Context(
                {
                    **self._content_context(),
                    "SOCIAL_BUTTONS": [
                        [hostile_name, "https://example.com/hostile"],
                        ["tiktok", "https://example.com/tiktok"],
                    ],
                }
            )
        )

        self.assertIn("association-footer", rendered)
        self.assertIn(f'<i class="fab {hostile_name}"></i>', rendered)
        self.assertIn('aria-label="TikTok"', rendered)

    def _render_impuls_footer(self, language="sv"):
        impuls_settings = importlib.import_module("core.settings.impuls")

        with (
            override_settings(
                TEMPLATES=impuls_settings.TEMPLATES,
                STATICFILES_DIRS=impuls_settings.STATICFILES_DIRS,
            ),
            translation.override(language),
        ):
            return render_to_string(
                "core/footer.html",
                {
                    **self._content_context(),
                    "SOCIAL_BUTTONS": impuls_settings.CONTENT_VARIABLES["SOCIAL_BUTTONS"],
                },
            )

    def test_impuls_footer_renders_its_configured_social_icons(self):
        rendered = self._render_impuls_footer()

        self.assertIn('<i class="fab fa-facebook-f"></i>', rendered)
        self.assertIn('<i class="fab fa-instagram"></i>', rendered)
        self.assertIn('aria-label="TikTok"', rendered)
        self.assertIn('aria-label="Linktree"', rendered)
        self.assertNotIn("fab tiktok", rendered)
        self.assertNotIn("fab linktree", rendered)
        # The Impuls footer overrides footer_logo, so this asset proves which
        # template rendered and not just that the shared footer was used.
        self.assertIn("impuls-logo-transparent.png", rendered)
        self.assertNotIn("core/images/footerlogo.png", rendered)


class SocialIconTemplateTagTests(SimpleTestCase):
    def test_returns_the_shared_svg_template_when_one_exists(self):
        self.assertEqual(social_icon_template("tiktok"), "core/svg/social/tiktok.svg")
        self.assertEqual(social_icon_template("linktree"), "core/svg/social/linktree.svg")

    def test_returns_empty_for_icon_font_classes_without_an_svg(self):
        self.assertEqual(social_icon_template("fa-facebook-f"), "")

    def test_rejects_names_that_could_escape_the_icon_directory(self):
        for name in ("../../../svg/albin", "core/footer", "TikTok", "tiktok.svg", "", None):
            with self.subTest(name=name):
                self.assertEqual(social_icon_template(name), "")

    def test_rejects_names_longer_than_the_filesystem_limit(self):
        # A 300 character name is longer than the per-name filesystem limit, so
        # the lookup must be refused instead of raising OSError.
        self.assertEqual(social_icon_template("a" * 300), "")


class HealthCheckTests(TestCase):
    def test_healthz_does_not_require_dependencies(self):
        response = self.client.get(reverse("healthz"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})

    def test_readyz_checks_runtime_dependencies(self):
        response = self.client.get(reverse("readyz"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})

    @override_settings(CACHES={"default": {"BACKEND": "django.core.cache.backends.dummy.DummyCache"}})
    def test_readyz_allows_dummy_cache(self):
        response = self.client.get(reverse("readyz"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})


class HomepageContextHelperTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.author = get_user_model().objects.create_user(
            username="homepage-author",
            password="pass",
            email="homepage-author@example.com",
        )
        cls.albins_angels = Category.objects.create(
            name="Albins Angels",
            slug="albins-angels",
        )

    def _post(self, title, published_time, published=True):
        return Post.objects.create(
            title=title,
            slug=title.lower().replace(" ", "-"),
            category=self.albins_angels,
            author=self.author,
            published_time=published_time if published else None,
        )

    def test_recent_albins_angels_post_returns_newest_recent_published_post(self):
        now = timezone.now()
        older = self._post("Older recent", now - timedelta(days=2))
        newest = self._post("Newest recent", now - timedelta(hours=1))
        self._post("Too old", now - timedelta(days=11))
        self._post("Draft recent", now - timedelta(minutes=30), published=False)
        self._post("Scheduled future", now + timedelta(hours=1))

        self.assertEqual(get_recent_albins_angels_post(now=now), newest)
        self.assertNotEqual(get_recent_albins_angels_post(now=now), older)

    def test_recent_albins_angels_post_returns_none_without_recent_posts(self):
        now = timezone.now()
        self._post("Too old", now - timedelta(days=11))

        self.assertIsNone(get_recent_albins_angels_post(now=now))

    def test_format_calendar_events_keys_by_start_date(self):
        event_start = timezone.now() + timedelta(days=1)
        event = Event.objects.create(
            title="Calendar Event",
            slug="calendar-event",
            author=self.author,
            event_date_start=event_start,
            event_date_end=event_start + timedelta(hours=2),
        )

        payload = format_calendar_events([event])

        event_key = event_start.strftime("%Y-%m-%d")
        day_events = payload[event_key]
        self.assertEqual(len(day_events), 1)
        self.assertEqual(
            day_events[0]["link"],
            reverse("events:detail", kwargs={"slug": event.slug}),
        )
        self.assertEqual(day_events[0]["eventTitle"], event.title)
        self.assertEqual(day_events[0]["eventFullDate"], event.event_date_start)

    def test_format_calendar_events_keeps_all_events_on_the_same_day(self):
        event_start = timezone.localtime(timezone.now()).replace(
            hour=10, minute=0, second=0, microsecond=0
        ) + timedelta(days=1)
        first = Event.objects.create(
            title="First Event",
            slug="first-event",
            author=self.author,
            event_date_start=event_start,
            event_date_end=event_start + timedelta(hours=1),
        )
        second = Event.objects.create(
            title="Second Event",
            slug="second-event",
            author=self.author,
            event_date_start=event_start + timedelta(hours=3),
            event_date_end=event_start + timedelta(hours=4),
        )

        payload = format_calendar_events([first, second])

        event_key = event_start.strftime("%Y-%m-%d")
        day_events = payload[event_key]
        self.assertEqual(len(day_events), 2)
        self.assertEqual(
            [event["eventTitle"] for event in day_events],
            [first.title, second.title],
        )
        self.assertEqual(
            day_events[1]["link"],
            reverse("events:detail", kwargs={"slug": second.slug}),
        )


class AuditLogTestCase(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_superuser(
            username="admin",
            password="pass",
            email="admin@example.com",
        )
        queryset = get_user_model().objects.filter(pk=self.user.pk)
        LogEntry.objects.log_actions(
            user_id=self.user.pk,
            queryset=queryset,
            action_flag=ADDITION,
            change_message="created user",
            single_object=True,
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

    def test_admin_shows_language_switcher_when_enabled(self):
        self.client.login(username="admin", password="pass")
        self.client.cookies[settings.LANGUAGE_COOKIE_NAME] = "en"
        response = self.client.get(reverse("admin:admin_logentry_changelist"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="admin-language-switcher"')
        self.assertContains(response, f'action="{reverse("set_lang")}"')

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
            reverse("set_lang"),
            {"lang": "fi"},
            HTTP_REFERER=reverse("index"),
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.cookies[settings.LANGUAGE_COOKIE_NAME].value, "fi")
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

    def test_set_language_falls_back_to_homepage_without_referer(self):
        response = self.client.post(
            reverse("set_lang"),
            {"lang": "sv"},
        )
        self.assertEqual(response.status_code, 302)
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

    def test_homepage_skips_events_without_slugs(self):
        author = get_user_model().objects.create_user(username="event-author")
        Event.objects.create(
            title="Broken Event",
            slug="",
            author=author,
            event_date_start=timezone.now(),
            event_date_end=timezone.now() + timedelta(days=1),
        )

        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Broken Event")

    def test_homepage_defaults_to_swedish_without_cookie_or_header(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.wsgi_request.LANGUAGE_CODE, settings.LANGUAGE_CODE)

    def test_accept_language_header_is_ignored_when_browser_detection_is_disabled(self):
        response = self.client.get("/", HTTP_ACCEPT_LANGUAGE="en")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.wsgi_request.LANGUAGE_CODE, "sv")

    @override_settings(USE_ACCEPT_LANGUAGE_HEADER=True)
    def test_accept_language_header_can_set_language_when_enabled(self):
        response = self.client.get("/", HTTP_ACCEPT_LANGUAGE="en")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.wsgi_request.LANGUAGE_CODE, "en")

    def test_cookie_takes_precedence_over_accept_language_header(self):
        self.client.cookies[settings.LANGUAGE_COOKIE_NAME] = "fi"
        response = self.client.get("/", HTTP_ACCEPT_LANGUAGE="en")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.wsgi_request.LANGUAGE_CODE, "fi")

    def test_404_page_renders_in_finnish_via_cookie(self):
        self.client.cookies[settings.LANGUAGE_COOKIE_NAME] = "fi"
        response = self.client.get("/this-page-does-not-exist/")
        self.assertEqual(response.status_code, 404)
        self.assertContains(response, "Sivua ei löydetty", status_code=404)

    def test_homepage_renders_language_switcher_in_english_via_cookie(self):
        self.client.cookies[settings.LANGUAGE_COOKIE_NAME] = "en"
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.wsgi_request.LANGUAGE_CODE, "en")
        self.assertContains(response, "Language")

    def test_homepage_renders_language_switcher_in_finnish_via_cookie(self):
        self.client.cookies[settings.LANGUAGE_COOKIE_NAME] = "fi"
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.wsgi_request.LANGUAGE_CODE, "fi")
        self.assertContains(response, '<span class="language-dropdown-current">FI</span>', html=True)

    def test_homepage_preserves_swedish_labels_by_default(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.wsgi_request.LANGUAGE_CODE, "sv")
        self.assertContains(response, "Adress")
        self.assertContains(response, "Joke")

    def test_404_page_renders_in_english_via_cookie(self):
        self.client.cookies[settings.LANGUAGE_COOKIE_NAME] = "en"
        response = self.client.get("/this-page-does-not-exist/")
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

    def test_500_page_renders_in_selected_swedish_language(self):
        request = self.factory.get("/")
        with translation.override("sv"):
            response = handler500(request)
        self.assertEqual(response.status_code, 500)
        self.assertContains(response, "Serverfel", status_code=500)

    def test_error_handlers_close_stale_connections_before_rendering(self):
        # The ASGI error path can reuse a connection that died on a previous
        # per-request thread; the handlers must close it before rendering so
        # the error page itself does not 500 with "connection already closed".
        request = self.factory.get("/")
        with patch("date.views.close_old_connections") as close:
            handler404(request)
            handler500(request)
        self.assertEqual(close.call_count, 2)

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
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.wsgi_request.LANGUAGE_CODE, "sv")
        self.assertNotContains(response, 'action="')
        self.assertNotContains(response, 'name="lang"')

    @override_settings(
        ENABLE_LANGUAGE_FEATURES=True,
        LANGUAGES=(("sv", "Svenska"), ("en", "English")),
    )
    def test_set_language_falls_back_to_default_when_language_is_not_offered(self):
        response = self.client.post(
            reverse("set_lang"),
            {"lang": "fi"},
            HTTP_REFERER=reverse("index"),
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response.cookies[settings.LANGUAGE_COOKIE_NAME].value,
            settings.LANGUAGE_CODE,
        )

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

    def test_localized_timeuntil_filter_returns_empty_for_past_timestamps_in_all_languages(self):
        # The suffix is rendered after a date, e.g. "1.10 01:23, om 2 timmar".
        # A past timestamp must contribute nothing at all, so the rendering has
        # to equal the date on its own. Comparing against that instead of
        # scanning the combined string for ", " and "0 " keeps the check
        # independent of how the date formats: "1.10 " contains "0 " by itself.
        template = Template(
            '{% load localized_time %}{{ value|date:"j.n H:i" }}{{ value|localized_timeuntil|comma_if }}'
        )
        date_only = Template('{{ value|date:"j.n H:i" }}')
        value = timezone.now() - timedelta(minutes=1)

        for language in ("sv", "en", "fi"):
            with self.subTest(language=language), translation.override(language):
                rendered = template.render(Context({"value": value}))
                expected = date_only.render(Context({"value": value}))
            self.assertEqual(rendered, expected)

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

    def test_localized_remaining_places_filter_uses_finnish_singular(self):
        template = Template("{% load localized_time %}{{ value|localized_remaining_places }}")
        with translation.override("fi"):
            rendered = template.render(Context({"value": 1}))
        self.assertEqual(rendered, "1 paikka jäljellä!")

    def test_localized_remaining_places_filter_uses_english_word_order(self):
        template = Template("{% load localized_time %}{{ value|localized_remaining_places }}")
        with translation.override("en"):
            rendered = template.render(Context({"value": 80}))
        self.assertEqual(rendered, "80 spots left!")

    def test_localized_remaining_places_filter_uses_english_singular(self):
        template = Template("{% load localized_time %}{{ value|localized_remaining_places }}")
        with translation.override("en"):
            rendered = template.render(Context({"value": 1}))
        self.assertEqual(rendered, "1 spot left!")

    def test_localized_remaining_places_filter_uses_swedish_word_order(self):
        template = Template("{% load localized_time %}{{ value|localized_remaining_places }}")
        with translation.override("sv"):
            rendered = template.render(Context({"value": 80}))
        self.assertEqual(rendered, "Det finns 80 platser kvar!")

    def test_localized_remaining_places_filter_uses_swedish_singular(self):
        template = Template("{% load localized_time %}{{ value|localized_remaining_places }}")
        with translation.override("sv"):
            rendered = template.render(Context({"value": 1}))
        self.assertEqual(rendered, "Det finns 1 plats kvar!")

    def test_footer_skips_social_buttons_without_urls(self):
        template = Template("{% include 'core/footer.html' %}")
        rendered = template.render(
            Context(
                {
                    "SOCIAL_BUTTONS": [
                        ["fa-facebook-f", "https://example.com/facebook"],
                        ["fa-github", ""],
                    ],
                    "ASSOCIATION_NAME_FULL": "Test Association",
                    "ASSOCIATION_EMAIL": "test@example.com",
                    "ASSOCIATION_ADDRESS_L1": "Line 1",
                    "ASSOCIATION_ADDRESS_L2": "Line 2",
                    "ASSOCIATION_POSTAL_CODE": "12345",
                    "ASSOCIATION_OFFICE_HOURS": "",
                }
            )
        )
        self.assertIn("https://example.com/facebook", rendered)
        self.assertNotIn('href=""', rendered)


class AssociationLanguageSettingsTests(SimpleTestCase):
    """Biocum narrows the shared language list to Swedish and English, like
    date and impuls do, so the published flag never exposes Finnish."""

    def _biocum_languages(self, enable_language_features):
        common = importlib.import_module("core.settings.common")
        biocum = importlib.import_module("core.settings.biocum")
        # The module reads ENABLE_LANGUAGE_FEATURES at import time, so reload
        # it under the requested flag and restore its import-time state after
        # the test.
        self.addCleanup(importlib.reload, biocum)
        with patch.object(common, "ENABLE_LANGUAGE_FEATURES", enable_language_features):
            return importlib.reload(biocum).LANGUAGES

    def test_biocum_offers_swedish_and_english_when_language_features_enabled(self):
        self.assertEqual(
            self._biocum_languages(True),
            (("sv", "Svenska"), ("en", "English")),
        )

    def test_biocum_offers_swedish_only_when_language_features_disabled(self):
        self.assertEqual(
            self._biocum_languages(False),
            (("sv", "Svenska"),),
        )


class ConnectionLifecycleMiddlewareTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def test_runs_lifecycle_around_response(self):
        # Django's ASGI handler dispatches request_started/request_finished
        # on the event loop thread, so close_old_connections must also run
        # on the executor thread that owns the connection, via this
        # middleware: once before the request (drop obsolete/poisoned
        # connections) and once after (close or keep per CONN_MAX_AGE).
        middleware = ConnectionLifecycleMiddleware(lambda request: HttpResponse("ok"))
        with patch("date.middleware.close_old_connections") as close:
            response = middleware(self.factory.get("/"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(close.call_count, 2)

    def test_runs_lifecycle_when_view_raises(self):
        def boom(request):
            raise RuntimeError("boom")

        middleware = ConnectionLifecycleMiddleware(boom)
        with patch("date.middleware.close_old_connections") as close:
            with self.assertRaises(RuntimeError):
                middleware(self.factory.get("/"))
        self.assertEqual(close.call_count, 2)


class HomepageTemplateSelectionTests(TestCase):
    @override_settings(APRIL_HOMEPAGE_ENABLED=True)
    @patch("date.views.timezone.localdate", return_value=date(2026, 4, 1))
    @patch("date.views.secrets.randbelow", return_value=0)
    def test_april_template_served_on_april_first_when_roll_matches(self, _randrange, _localdate):
        self.assertEqual(get_homepage_template_name(), "date/april_start.html")

    @override_settings(APRIL_HOMEPAGE_ENABLED=True)
    @patch("date.views.timezone.localdate", return_value=date(2026, 4, 1))
    @patch("date.views.secrets.randbelow", return_value=1)
    def test_regular_template_served_on_april_first_when_roll_misses(self, _randrange, _localdate):
        self.assertEqual(get_homepage_template_name(), "date/start.html")

    @override_settings(APRIL_HOMEPAGE_ENABLED=True)
    @patch("date.views.timezone.localdate", return_value=date(2026, 4, 2))
    def test_regular_template_served_outside_april_first(self, _localdate):
        self.assertEqual(get_homepage_template_name(), "date/start.html")

    @patch("date.views.timezone.localdate", return_value=date(2026, 4, 1))
    @patch("date.views.secrets.randbelow", return_value=0)
    def test_april_template_never_served_when_disabled(self, _randrange, _localdate):
        self.assertEqual(get_homepage_template_name(), "date/start.html")


class AssociationHomepageSmokeTests(TestCase):
    association_settings_modules = ASSOCIATION_SETTINGS_MODULES

    def _association_overrides(self, association):
        settings_module = importlib.import_module(self.association_settings_modules[association])
        installed_apps = [app for app in settings_module.INSTALLED_APPS if app != "django_cleanup"]
        overrides = {
            "PROJECT_NAME": association,
            "INSTALLED_APPS": installed_apps,
            "ROOT_URLCONF": settings_module.ROOT_URLCONF,
            "TEMPLATES": settings_module.TEMPLATES,
            "CONTENT_VARIABLES": settings_module.CONTENT_VARIABLES,
            "STAFF_GROUPS": settings_module.STAFF_GROUPS,
            "STATICFILES_DIRS": settings_module.STATICFILES_DIRS,
            "ARCHIVE_ENABLED": getattr(settings_module, "ARCHIVE_ENABLED", True),
            "MEMBERS_SIGNUP_ENABLED": getattr(settings_module, "MEMBERS_SIGNUP_ENABLED", True),
            "BILLING_CONTEXT": getattr(settings_module, "BILLING_CONTEXT", {}),
            "EXPERIMENTAL_FEATURES": getattr(settings_module, "EXPERIMENTAL_FEATURES", []),
            "APRIL_HOMEPAGE_ENABLED": getattr(settings_module, "APRIL_HOMEPAGE_ENABLED", False),
            "REGISTRATION_TERMS_ENABLED": getattr(settings_module, "REGISTRATION_TERMS_ENABLED", False),
            "EQUALITY_PLAN_ENABLED": getattr(settings_module, "EQUALITY_PLAN_ENABLED", False),
            "KK_EVENT_TEMPLATES_ENABLED": getattr(settings_module, "KK_EVENT_TEMPLATES_ENABLED", False),
            # Only DaTe installs the booking app; without this the test
            # settings' True would leak into the other variants' homepages.
            "BOOKING_ENABLED": getattr(settings_module, "BOOKING_ENABLED", False),
        }
        return overrides

    def _clear_routing_caches(self):
        clear_url_caches()
        set_urlconf(None)

    def _get_association_homepage(self, association, **extra_overrides):
        default_admin_registry = admin.site._registry.copy()
        custom_admin_registry = admin_site._registry.copy()
        with override_settings(**self._association_overrides(association), **extra_overrides):
            self._clear_routing_caches()
            try:
                return self.client.get("/")
            finally:
                admin.site._registry = default_admin_registry
                admin_site._registry = custom_admin_registry
                self._clear_routing_caches()

    def test_association_homepages_render(self):
        for association in self.association_settings_modules:
            with self.subTest(association=association):
                response = self._get_association_homepage(association)
                self.assertEqual(response.status_code, 200)

    def test_biocum_homepage_offers_swedish_and_english_only(self):
        biocum_settings = importlib.import_module("core.settings.biocum")
        cache.clear()
        response = self._get_association_homepage(
            "biocum",
            ENABLE_LANGUAGE_FEATURES=True,
            LANGUAGES=biocum_settings.DATE_LANGUAGES,
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'action="/set_lang/"')
        self.assertContains(response, 'name="lang"')
        self.assertContains(response, "Svenska")
        self.assertContains(response, "English")
        self.assertNotContains(response, "Suomi")
        self.assertNotContains(response, 'value="fi"')

    @patch("date.views.timezone.localdate", return_value=date(2026, 4, 1))
    @patch("date.views.secrets.randbelow", return_value=0)
    def test_kk_april_homepage_renders(self, _randrange, _localdate):
        response = self._get_association_homepage("kk")

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "date/april_start.html")

    def test_impuls_homepage_shows_instagram_slider_instead_of_partners(self):
        cache.clear()
        IgUrl.objects.create(image="instagram/impuls-post.png", shortcode="ImpulsPost1")
        AdUrl.objects.create(ad_url="https://example.com/partner-logo.png", company_url="https://example.com/partner")

        response = self._get_association_homepage("impuls")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'href="https://www.instagram.com/p/ImpulsPost1/"')
        self.assertContains(response, "--ig-items: 32")
        self.assertContains(response, '<h3 class="ig-title header-border-bottom">Senaste Instagram-inlägg</h3>')
        original, *repeats = re.findall(
            r'<a href="https://www\.instagram\.com/p/ImpulsPost1/"([^>]*)>', response.content.decode()
        )
        self.assertEqual(len(repeats), 31)
        self.assertNotIn("aria-hidden", original)
        self.assertTrue(all('aria-hidden="true"' in attrs and 'tabindex="-1"' in attrs for attrs in repeats))
        self.assertNotContains(response, "Samarbetspartners")
        self.assertNotContains(response, "https://example.com/partner-logo.png")

    def test_impuls_homepage_omits_instagram_slider_without_posts(self):
        cache.clear()

        response = self._get_association_homepage("impuls")

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'class="ig-scroll"')
        self.assertNotContains(response, "Senaste Instagram-inlägg")

    def test_impuls_instagram_heading_is_translated_to_english(self):
        impuls_settings = importlib.import_module("core.settings.impuls")
        cache.clear()
        IgUrl.objects.create(image="instagram/impuls-post.png", shortcode="ImpulsPost1")
        self.client.cookies[settings.LANGUAGE_COOKIE_NAME] = "en"

        response = self._get_association_homepage(
            "impuls",
            ENABLE_LANGUAGE_FEATURES=True,
            LANGUAGES=impuls_settings.DATE_LANGUAGES,
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, ">Latest Instagram posts</h3>")

    @patch("date.views.timezone.localdate", return_value=date(2026, 10, 6))
    def test_kk_homepage_uses_the_shared_instagram_slider(self, _localdate):
        cache.clear()
        IgUrl.objects.create(url="https://cdn.example/kk-post.jpg", shortcode="KkPost1")

        response = self._get_association_homepage("kk")

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "date/components/instagram.html")
        self.assertContains(response, 'href="https://www.instagram.com/p/KkPost1/"')
        self.assertNotContains(response, "ig-title")


class HomepageQueryTests(TestCase):
    """The homepage evaluates each data queryset exactly once and caches the
    assembled context for anonymous visitors. The version key is bumped on
    every Event/Post/AdUrl/IgUrl save or delete, so admin edits invalidate
    the cache immediately and the 300s TTL is only a backstop; development
    uses the dummy cache, so caching is off there."""

    @classmethod
    def setUpTestData(cls):
        cls.author = get_user_model().objects.create_user(username="homepage-query-author")
        cls.albins_angels = Category.objects.create(name="Albins Angels", slug="albins-angels")
        Post.objects.create(
            title="Uncategorized news",
            slug="uncategorized-news",
            author=cls.author,
            category=None,
            published_time=timezone.now(),
        )

    def test_homepage_context_uses_six_queries(self):
        cache.clear()
        # One query per homepage source: events, news, ads, instagram posts,
        # Albins Angels, and the booking block (DaTe has BOOKING_ENABLED on).
        with self.assertNumQueries(6):
            _homepage_context()

    def test_anonymous_homepage_is_cached_after_first_load(self):
        cache.clear()
        with CaptureQueriesContext(connection) as first:
            self.client.get("/")
        with CaptureQueriesContext(connection) as second:
            response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        # Second load reuses the cached homepage context and anonymous
        # navigation; the remaining query is the footer Albins Angels category
        # lookup, which runs on every page since the badge resolves by name.
        self.assertLess(len(second), len(first))
        self.assertEqual(len(second), 1)

    def test_logged_in_homepage_is_not_cached(self):
        cache.clear()
        user = get_user_model().objects.create_user(username="member-user", password="pass")
        self.client.force_login(user)
        with CaptureQueriesContext(connection) as first:
            self.client.get("/")
        with CaptureQueriesContext(connection) as second:
            self.client.get("/")
        self.assertEqual(len(first), len(second))

    def test_cache_serves_latest_events_after_ttl_expiry(self):
        cache.clear()
        with patch("date.views.HOMEPAGE_CACHE_TTL", 1):
            self.client.get("/")
            author = get_user_model().objects.create_user(username="event-author-2")
            Event.objects.create(
                title="Fresh Event",
                slug="fresh-event",
                author=author,
                event_date_start=timezone.now(),
                event_date_end=timezone.now() + timedelta(days=1),
            )
            # Wait out the 1s TTL: the cached context must expire and the
            # next anonymous load must include the new event. Assert on the
            # view context; the template fragment cache would mask the HTML.
            time.sleep(1.1)
            response = self.client.get("/")
        self.assertIn("Fresh Event", [event.title for event in response.context["events"]])

    def test_cache_key_is_isolated_by_language(self):
        cache.clear()
        with self.assertNumQueries(9):
            self.client.get("/")
        # A different active language must not reuse the Swedish entry (set
        # via the language cookie; the locale middleware drives get_language).
        self.client.cookies[settings.LANGUAGE_COOKIE_NAME] = "fi"
        with self.assertNumQueries(9):
            self.client.get("/")

    def test_admin_edit_invalidates_anonymous_cache(self):
        cache.clear()
        self.client.get("/")
        author = get_user_model().objects.create_user(username="invalidation-author")
        with self.captureOnCommitCallbacks(execute=True):
            Post.objects.create(
                title="Fresh Invalidation News",
                slug="fresh-invalidation-news",
                author=author,
                category=None,
                published_time=timezone.now(),
            )
        # The version key was bumped on commit, so the next anonymous load
        # rebuilds the context and shows the new post without waiting out
        # the TTL.
        response = self.client.get("/")
        self.assertIn(
            "Fresh Invalidation News",
            [post.title for post in response.context["news"]],
        )

    def test_event_save_invalidates_anonymous_cache(self):
        cache.clear()
        self.client.get("/")
        author = get_user_model().objects.create_user(username="invalidation-event-author")
        with self.captureOnCommitCallbacks(execute=True):
            Event.objects.create(
                title="Fresh Invalidation Event",
                slug="fresh-invalidation-event",
                author=author,
                event_date_start=timezone.now(),
                event_date_end=timezone.now() + timedelta(days=1),
            )
        response = self.client.get("/")
        self.assertIn(
            "Fresh Invalidation Event",
            [event.title for event in response.context["events"]],
        )

    def test_admin_delete_invalidates_anonymous_cache(self):
        cache.clear()
        self.client.get("/")
        with self.captureOnCommitCallbacks(execute=True):
            Post.objects.filter(slug="uncategorized-news").delete()
        response = self.client.get("/")
        self.assertNotIn(
            "Uncategorized news",
            [post.title for post in response.context["news"]],
        )

    def test_version_key_eviction_never_resurrects_stale_entries(self):
        cache.clear()
        self.client.get("/")
        # Simulate the version key being evicted while the homepage entry
        # is still alive: the next load must not reuse the old generation.
        cache.delete(_homepage_version_key())
        # The context rebuilds from scratch (7 queries, including the footer
        # Albins Angels category lookup); the navigation is still served from
        # its own cache.
        with self.assertNumQueries(7):
            self.client.get("/")

    def test_dummy_cache_never_caches(self):
        cache.clear()
        with override_settings(CACHES={"default": {"BACKEND": "django.core.cache.backends.dummy.DummyCache"}}):
            with self.assertNumQueries(9):
                self.client.get("/")
            with self.assertNumQueries(9):
                self.client.get("/")


class CalendarClickDayCompatibilityTests(SimpleTestCase):
    """Bind the calendar handler to the vendored library's own call signature.

    The homepage handler previously read the selected day without checking what
    the library passes as the callback's second argument. vanilla-calendar 1.x
    passes the selected dates array, 2.x passes the calendar instance, so the
    handler must accept either. Reading the signature out of the vendored file
    makes this fail loudly if the library is swapped without updating the
    handler, rather than only failing in a browser when a day is clicked.
    """

    repo_root = Path(__file__).resolve().parent.parent
    library_path = repo_root / "static/common/date/js/vanilla-calendar.min.js"
    partial_path = repo_root / "templates/common/date/partials/calendar_scripts.html"

    _click_day_pattern = re.compile(r"actions\.clickDay\s*&&\s*[\w$.]+\.clickDay\(([^)]*)\)")

    def _click_day_second_argument(self, source):
        match = self._click_day_pattern.search(source)
        if match is None:
            self.fail(
                "Could not find the clickDay invocation in "
                f"{self.library_path.relative_to(self.repo_root)}; update this test "
                "if the minified output changed."
            )
        arguments = [part.strip() for part in match.group(1).split(",")]
        if len(arguments) != 2:
            self.fail(f"Expected clickDay to be called with two arguments, got {arguments!r}")
        return arguments[1]

    def test_handler_matches_the_vendored_library_callback(self):
        source = self.library_path.read_text(encoding="utf-8")
        second_argument = self._click_day_second_argument(source)
        handler = self.partial_path.read_text(encoding="utf-8")

        # The handler must read whichever shape the vendored library passes. A
        # property access on the instance means the second argument is the calendar
        # itself, so the handler reads its selectedDates; a bare expression means
        # the argument already is the dates, and the handler must accept an array.
        if second_argument.split(".")[-1] == "selectedDates":
            self.assertIn(
                "Array.isArray(date)",
                handler,
                f"The vendored calendar passes {second_argument!r}, which is already the "
                "selected dates array, so the handler must accept an array.",
            )
        else:
            self.assertIn(
                "date.selectedDates",
                handler,
                f"The vendored calendar passes {second_argument!r}, so the handler must "
                "read the dates from that object.",
            )


@unittest.skipUnless(apps.is_installed('booking'), 'the booking app is not installed for this association')
class HomepageBookingTests(TestCase):
    """The homepage booking block: active rooms, the next 7 days, five entries.

    The assertions read ``response.context``: templates/date/date/start.html
    wraps the body in a 300 second ``{% cache %}`` fragment whose key does not
    carry the homepage version, so the HTML can lag behind an invalidation.
    Only DaTe installs the booking app, so this class runs with the capability
    on (core.settings.test pins BOOKING_ENABLED = True).
    """

    def setUp(self):
        # Imported here rather than at module level: `date` is installed for
        # every association while only DaTe installs the booking app, so a
        # module-level import would break the suite under any other settings
        # module. The class is skipped when the app is absent.
        from booking import access
        from booking.models import Booking, Room

        self.access = access
        self.Booking = Booking
        self.Room = Room
        cache.clear()
        self.now = timezone.now()
        self.room = self.Room.objects.create(name="Bastun")

    def _booking(self, room, start, **kwargs):
        return self.Booking.objects.create(room=room, start=start, end=start + timedelta(hours=1), **kwargs)

    def _booking_ids(self, response):
        return [booking.pk for booking in response.context["bookings"]]

    def test_homepage_context_includes_bookings_within_the_next_week(self):
        booking = self._booking(self.room, self.now + timedelta(days=2))

        self.assertEqual(self._booking_ids(self.client.get("/")), [booking.pk])

    def test_homepage_context_excludes_later_bookings(self):
        self._booking(self.room, self.now + timedelta(days=8))

        self.assertEqual(_homepage_context(now=self.now)["bookings"], [])

    def test_homepage_context_keeps_a_booking_exactly_seven_days_ahead(self):
        booking = self._booking(self.room, self.now + timedelta(days=7))

        self.assertEqual(
            [entry.pk for entry in _homepage_context(now=self.now)["bookings"]],
            [booking.pk],
        )

    def test_homepage_context_returns_at_most_five_bookings(self):
        starts = [self.now + timedelta(days=1, hours=index) for index in range(6)]
        bookings = [self._booking(self.room, start) for start in starts]

        self.assertEqual(
            [entry.pk for entry in _homepage_context(now=self.now)["bookings"]],
            [booking.pk for booking in bookings[:5]],
        )

    @override_settings(BOOKING_ENABLED=False)
    def test_homepage_context_has_no_bookings_without_the_capability(self):
        self._booking(self.room, self.now + timedelta(days=2))

        self.assertEqual(_homepage_context(now=self.now)["bookings"], [])

    @override_settings(BOOKING_ENABLED=False)
    def test_homepage_hides_the_booking_block_without_the_capability(self):
        self._booking(self.room, self.now + timedelta(days=2))

        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Bastun")

    def test_homepage_render_never_exposes_private_booking_data(self):
        start = self.now + timedelta(days=2)
        self.Booking.objects.create(
            room=self.room,
            start=start,
            end=start + timedelta(hours=1),
            booker_name="Hemlig Bokare",
            booker_email="hemlig@example.com",
            description="Hemlig beskrivning",
        )

        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.room.name)
        self.assertEqual(
            [booking.room.name for booking in response.context["bookings"]],
            [self.room.name],
        )
        self.assertNotContains(response, self.access.current_code(self.room))
        self.assertNotContains(response, "Hemlig Bokare")
        self.assertNotContains(response, "hemlig@example.com")
        self.assertNotContains(response, "Hemlig beskrivning")

    def test_booking_save_invalidates_anonymous_cache(self):
        cache.clear()
        primed = self.client.get("/")
        self.assertEqual(primed.context["bookings"], [])
        start = self.now + timedelta(days=2)

        with self.captureOnCommitCallbacks(execute=True):
            booking = self._booking(self.room, start)

        self.assertEqual(self._booking_ids(self.client.get("/")), [booking.pk])

    def test_booking_delete_invalidates_anonymous_cache(self):
        cache.clear()
        booking = self._booking(self.room, self.now + timedelta(days=2))
        self.assertEqual(self._booking_ids(self.client.get("/")), [booking.pk])

        with self.captureOnCommitCallbacks(execute=True):
            booking.delete()

        self.assertEqual(self.client.get("/").context["bookings"], [])

    def test_room_save_invalidates_anonymous_cache(self):
        cache.clear()
        self._booking(self.room, self.now + timedelta(days=2))
        self.assertEqual(
            [booking.room.name for booking in self.client.get("/").context["bookings"]],
            ["Bastun"],
        )

        with self.captureOnCommitCallbacks(execute=True):
            self.room.name = "Ombyggd bastu"
            self.room.save()

        self.assertEqual(
            [booking.room.name for booking in self.client.get("/").context["bookings"]],
            ["Ombyggd bastu"],
        )

    def test_room_delete_invalidates_anonymous_cache(self):
        cache.clear()
        empty_room = self.Room.objects.create(name="Tomt utrymme")
        self.client.get("/")
        version_key = _homepage_version_key()
        version_before = cache.get(version_key)

        with self.captureOnCommitCallbacks(execute=True):
            empty_room.delete()

        # A room without bookings has no homepage-visible effect of its own, so
        # the invalidation is asserted on the version the context cache keys on.
        self.assertNotEqual(cache.get(version_key), version_before)

    def test_the_booking_card_links_to_the_room_it_shows(self):
        # The card names one room and one time, so following it has to open that
        # room rather than the room list.
        other_room = self.Room.objects.create(name="Sauna")
        self._booking(self.room, self.now + timedelta(days=2))
        self._booking(other_room, self.now + timedelta(days=3))

        response = self.client.get("/")

        self.assertContains(response, reverse("booking:room_detail", args=[self.room.pk]))
        self.assertContains(response, reverse("booking:room_detail", args=[other_room.pk]))
