from django.contrib import admin as django_admin
from django.contrib.auth import get_user_model
from django.apps import apps
from django.test import RequestFactory, TestCase, override_settings
from django.urls import NoReverseMatch, reverse

from core.admin_base import PublicUrlAdminMixin, UnfoldFormMixin
from core.settings.common import _get_unfold_environment
from core.admin_ui import (
    SIDEBAR_NAVIGATION,
    TOPBAR_QUICK_CREATE_LINKS,
    get_sidebar_navigation,
    get_topbar_quick_create_links,
)


class AdminUiRegistryTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def test_quick_create_links_require_permissions(self):
        request = self.factory.get("/admin/")
        request.user = get_user_model().objects.create_user(
            username="member",
            password="pass",
            email="member@example.com",
        )

        self.assertEqual(get_topbar_quick_create_links(request), [])

    def test_superuser_gets_registered_quick_create_links(self):
        request = self.factory.get("/admin/")
        request.user = get_user_model().objects.create_superuser(
            username="admin",
            password="pass",
            email="admin@example.com",
        )

        hrefs = {link["href"] for link in get_topbar_quick_create_links(request)}

        self.assertIn("/admin/events/event/add/", hrefs)
        self.assertIn("/admin/news/post/add/", hrefs)
        self.assertIn("/admin/staticpages/staticpage/add/", hrefs)

    def test_sidebar_registry_resolves_expected_groups(self):
        request = self.factory.get("/admin/")
        request.user = get_user_model().objects.create_superuser(
            username="sidebar-admin",
            password="pass",
            email="sidebar@example.com",
        )

        groups = get_sidebar_navigation(request)
        links = {
            item["link"]
            for group in groups
            for item in group["items"]
        }

        self.assertGreaterEqual(len(groups), 6)
        self.assertIn("/admin/members/member/", links)
        self.assertIn("/admin/events/event/", links)
        self.assertIn("/admin/staticpages/staticpage/", links)

    def test_sidebar_registry_requires_permissions(self):
        request = self.factory.get("/admin/")
        request.user = get_user_model().objects.create_user(
            username="sidebar-member",
            password="pass",
            email="sidebar-member@example.com",
        )

        self.assertEqual(get_sidebar_navigation(request), [])

    def test_sidebar_registry_omits_missing_urls(self):
        request = self.factory.get("/admin/")
        request.user = get_user_model().objects.create_superuser(
            username="sidebar-admin-2",
            password="pass",
            email="sidebar2@example.com",
        )

        links = {
            item["link"]
            for group in get_sidebar_navigation(request)
            for item in group["items"]
        }

        self.assertNotIn("", links)

    @override_settings(ALLOWED_HOSTS=["qa.date.example"])
    def test_unfold_environment_detects_qa_subdomain(self):
        request = self.factory.get("/admin/", HTTP_HOST="qa.date.example")

        label, variant = _get_unfold_environment(request)

        self.assertEqual(str(label), "Quality Assurance")
        self.assertEqual(variant, "warning")

    @override_settings(ALLOWED_HOSTS=["date.example"])
    def test_unfold_environment_returns_success_for_production(self):
        request = self.factory.get("/admin/", HTTP_HOST="date.example")

        label, variant = _get_unfold_environment(request)

        self.assertEqual(str(label), "Production")
        self.assertEqual(variant, "success")

    def test_registry_permission_strings_match_models(self):
        links = list(TOPBAR_QUICK_CREATE_LINKS)
        for group in SIDEBAR_NAVIGATION:
            links.extend(group.items)

        for link in links:
            if not link.permission:
                continue
            if link.url_name:
                try:
                    reverse(link.url_name)
                except NoReverseMatch:
                    continue
            app_label, codename = link.permission.split(".", 1)
            action, model_name = codename.split("_", 1)

            with self.subTest(permission=link.permission):
                self.assertIn(action, {"add", "change", "delete", "view"})
                self.assertIsNotNone(apps.get_model(app_label, model_name))


class PublicUrlAdminMixinTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()

        class _TestAdmin(PublicUrlAdminMixin, django_admin.ModelAdmin):
            pass

        from staticpages.models import StaticPage
        self.admin = _TestAdmin(StaticPage, django_admin.site)

    def test_public_url_returns_dash_for_none(self):
        self.assertEqual(self.admin.public_url(None), '-')

    def test_public_url_returns_dash_for_unsaved_object(self):
        from staticpages.models import StaticPage
        self.assertEqual(self.admin.public_url(StaticPage()), '-')

    def test_public_url_returns_link_for_saved_object(self):
        from staticpages.models import StaticPage
        obj = StaticPage.objects.create(slug='test-mixin', members_only=False)
        result = str(self.admin.public_url(obj))
        self.assertIn('href=', result)
        self.assertIn(obj.get_absolute_url(), result)

    def test_get_readonly_fields_includes_public_url_for_saved_object(self):
        from staticpages.models import StaticPage
        obj = StaticPage.objects.create(slug='test-ro', members_only=False)
        request = self.factory.get('/')
        self.assertIn('public_url', self.admin.get_readonly_fields(request, obj=obj))

    def test_get_readonly_fields_excludes_public_url_for_new_object(self):
        request = self.factory.get('/')
        self.assertNotIn('public_url', self.admin.get_readonly_fields(request, obj=None))


class UnfoldFormMixinTests(TestCase):
    def test_mixin_does_not_break_form_init(self):
        from django import forms

        class _SampleForm(UnfoldFormMixin, forms.Form):
            name = forms.CharField()
            url = forms.URLField()

        form = _SampleForm(data={'name': 'test', 'url': 'https://example.com'})
        self.assertTrue(form.is_valid())
