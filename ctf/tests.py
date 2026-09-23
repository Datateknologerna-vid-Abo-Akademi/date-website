from importlib import import_module

from django.conf import settings
from django.contrib import admin
from django.contrib.auth import get_user_model
from django.db import connection
from django.db.migrations.loader import MigrationLoader
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse
from django_ckeditor_5.widgets import CKEditor5Widget

from ctf.models import Ctf


class CtfTranslationAdminTests(TestCase):
    def setUp(self):
        self.admin_user = get_user_model().objects.create_superuser(
            username="ctf-translation-admin",
            password="pass",
            email="ctf-translation-admin@example.com",
        )
        self.client.force_login(self.admin_user)
        self.request_factory = RequestFactory()
        self.ctf = Ctf.objects.create(title="Spring CTF", slug="spring-ctf")

    def _translation_form(self):
        request = self.request_factory.get(reverse("admin:ctf_ctf_change", args=[self.ctf.pk]))
        request.user = self.admin_user
        return admin.site._registry[Ctf].get_form(request, obj=self.ctf)

    def test_change_page_renders_translation_fields(self):
        response = self.client.get(reverse("admin:ctf_ctf_change", args=[self.ctf.pk]))

        self.assertEqual(response.status_code, 200)
        for field_name in ("title_sv", "title_en", "title_fi", "content_sv"):
            self.assertContains(response, f'name="{field_name}"')

    def test_translation_form_uses_ckeditor_widget_for_content_fields(self):
        form_class = self._translation_form()

        for field_name in ("content_sv", "content_en", "content_fi"):
            self.assertIsInstance(form_class.base_fields[field_name].widget, CKEditor5Widget)

    @override_settings(LANGUAGES=(("sv", "Svenska"), ("en", "English")))
    def test_translation_form_hides_inactive_language_fields(self):
        form_class = self._translation_form()

        self.assertIn("title_en", form_class.base_fields)
        self.assertIn("content_en", form_class.base_fields)
        self.assertNotIn("title_fi", form_class.base_fields)
        self.assertNotIn("content_fi", form_class.base_fields)

    def test_translation_status_counts_completed_fields(self):
        model_admin = admin.site._registry[Ctf]

        self.assertEqual(model_admin.translation_status(self.ctf), "sv: 1/2; en: 0/2; fi: 0/2")
        self.assertEqual(
            model_admin.translation_status(Ctf(title="Spring CTF", content="<p>Come solve puzzles</p>")),
            "sv: 2/2; en: 0/2; fi: 0/2",
        )

    def test_changelist_shows_translation_coverage(self):
        response = self.client.get(reverse("admin:ctf_ctf_changelist"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "sv: 1/2; en: 0/2; fi: 0/2")

    @override_settings(ENABLE_LANGUAGE_FEATURES=False)
    def test_translation_coverage_is_hidden_when_language_features_are_disabled(self):
        model_admin = admin.site._registry[Ctf]
        request = self.request_factory.get(reverse("admin:ctf_ctf_changelist"))

        self.assertNotIn("translation_status", model_admin.get_list_display(request))


class CtfPublicTranslationTests(TestCase):
    def setUp(self):
        self.member = get_user_model().objects.create_user(username="ctf-member", password="pass")
        self.client.force_login(self.member)
        self.ctf = Ctf.objects.create(
            title="Vår CTF",
            content="<p>Svensk text</p>",
            title_en="Spring CTF",
            content_en="<p>English text</p>",
            slug="spring-ctf",
        )

    def test_detail_page_renders_the_selected_language(self):
        self.client.cookies[settings.LANGUAGE_COOKIE_NAME] = "en"

        response = self.client.get(reverse("ctf:detail", args=[self.ctf.slug]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Spring CTF")
        self.assertContains(response, "English text")
        self.assertNotContains(response, "Svensk text")

    def test_index_page_lists_titles_in_the_selected_language(self):
        self.client.cookies[settings.LANGUAGE_COOKIE_NAME] = "en"

        response = self.client.get(reverse("ctf:index"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Spring CTF")

    def test_detail_page_falls_back_to_swedish_when_a_translation_is_missing(self):
        self.ctf.title_en = ""
        self.ctf.content_en = ""
        self.ctf.save()
        self.client.cookies[settings.LANGUAGE_COOKIE_NAME] = "en"

        response = self.client.get(reverse("ctf:detail", args=[self.ctf.slug]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Vår CTF")
        self.assertContains(response, "Svensk text")


class CtfTranslationBackfillTests(TestCase):
    """Cover the 0006 backfill of the translated columns.

    ``Ctf.title`` and ``Ctf.content`` resolve through the modeltranslation
    descriptor, which only reads the ``*_<language>`` columns, so rows that
    predate the translated columns would render blank without the backfill.

    The historical model from the migration state is used on purpose: it has a
    plain manager, exactly like the model the migration runs against, while the
    live model's manager rewrites ``F("title")`` to the translated column and
    would turn the backfill into a no-op.
    """

    migration = "0005_ctf_content_en_ctf_content_fi_ctf_content_sv_and_more"

    def setUp(self):
        super().setUp()
        state = MigrationLoader(connection, ignore_no_migrations=True).project_state([("ctf", self.migration)])
        self.migration_apps = state.apps
        self.legacy_ctf = state.apps.get_model("ctf", "Ctf")

    def _run_backfill(self):
        module = import_module("ctf.migrations.0006_backfill_ctf_default_translations")
        module.backfill_ctf_default_translations(self.migration_apps, None)

    def test_backfill_copies_legacy_values_into_the_swedish_columns(self):
        ctf = self.legacy_ctf.objects.create(
            title="Legacy CTF",
            content="<p>Legacy text</p>",
            slug="legacy-ctf",
        )
        # Guard the test against becoming vacuous: a row written before the
        # translated columns existed has no Swedish values yet.
        self.assertIsNone(self.legacy_ctf.objects.values_list("title_sv", flat=True).get(pk=ctf.pk))

        self._run_backfill()

        row = self.legacy_ctf.objects.values("title_sv", "content_sv").get(pk=ctf.pk)
        self.assertEqual(row["title_sv"], "Legacy CTF")
        self.assertEqual(row["content_sv"], "<p>Legacy text</p>")
        # The public page reads through the live descriptor.
        self.assertEqual(Ctf.objects.get(pk=ctf.pk).title, "Legacy CTF")

    def test_backfill_keeps_existing_swedish_values(self):
        ctf = self.legacy_ctf.objects.create(
            title="Legacy CTF",
            content="<p>Legacy text</p>",
            slug="translated-ctf",
        )
        self.legacy_ctf.objects.filter(pk=ctf.pk).update(title_sv="Översatt titel", content_sv="<p>Översatt</p>")

        self._run_backfill()

        row = self.legacy_ctf.objects.values("title_sv", "content_sv").get(pk=ctf.pk)
        self.assertEqual(row["title_sv"], "Översatt titel")
        self.assertEqual(row["content_sv"], "<p>Översatt</p>")
