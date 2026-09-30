from django.apps import apps
from django.conf import settings
from django.contrib import admin as django_admin
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import RequestFactory, TestCase, override_settings
from django.urls import NoReverseMatch, reverse
from django.utils import translation

from core.admin_base import PublicUrlAdminMixin, UnfoldFormMixin
from core.admin_ui import (
    SIDEBAR_NAVIGATION,
    get_sidebar_navigation,
)
from core.admin_widgets import SafeAdminFileWidget, SafeAdminImageWidget, SafeAdminMultipleFileWidget
from core.settings.common import _get_unfold_environment


class AdminUiRegistryTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def test_sidebar_registry_resolves_expected_groups(self):
        request = self.factory.get("/admin/")
        request.user = get_user_model().objects.create_superuser(
            username="sidebar-admin",
            password="pass",
            email="sidebar@example.com",
        )

        groups = get_sidebar_navigation(request)
        links = {item["link"] for group in groups for item in group["items"]}

        self.assertGreaterEqual(len(groups), 6)
        self.assertIn("/admin/members/member/", links)
        self.assertIn("/admin/events/event/", links)
        self.assertIn("/admin/staticpages/staticpage/", links)
        self.assertIn("/admin/billing/eventbillingconfiguration/", links)
        self.assertIn("/admin/functionaries/functionaryrole/", links)
        self.assertIn("/admin/publications/publicationcollection/", links)
        self.assertIn("/admin/ctf/ctf/", links)
        self.assertNotIn("/admin/billing/eventinvoice/", links)
        self.assertNotIn("/admin/functionaries/functionary/", links)
        self.assertNotIn("/admin/publications/pdffile/", links)
        self.assertNotIn("/admin/ctf/guess/", links)

    def test_sidebar_registry_requires_permissions(self):
        request = self.factory.get("/admin/")
        request.user = get_user_model().objects.create_user(
            username="sidebar-member",
            password="pass",
            email="sidebar-member@example.com",
        )

        self.assertEqual(get_sidebar_navigation(request), [])

    def test_sidebar_accepts_change_permission_as_view_access(self):
        request = self.factory.get('/admin/')
        request.user = get_user_model().objects.create_user(
            username='change-only-admin',
            password='pass',
            email='change-only@example.com',
        )
        request.user.user_permissions.add(Permission.objects.get(codename='change_event'))

        links = {item['link'] for group in get_sidebar_navigation(request) for item in group['items']}

        self.assertIn('/admin/events/event/', links)

    def test_sidebar_registry_omits_missing_urls(self):
        request = self.factory.get("/admin/")
        request.user = get_user_model().objects.create_superuser(
            username="sidebar-admin-2",
            password="pass",
            email="sidebar2@example.com",
        )

        links = {item["link"] for group in get_sidebar_navigation(request) for item in group["items"]}

        self.assertNotIn("", links)

    @override_settings(ALLOWED_HOSTS=["qa.date.example"])
    def test_unfold_environment_detects_qa_subdomain(self):
        request = self.factory.get("/admin/", HTTP_HOST="qa.date.example")

        label, variant = _get_unfold_environment(request)

        with translation.override("en"):
            self.assertEqual(str(label), "Quality Assurance")
        self.assertEqual(variant, "warning")

    @override_settings(ALLOWED_HOSTS=["date.example"], DEBUG=False, DEVELOP=False)
    def test_unfold_environment_returns_success_for_production(self):
        request = self.factory.get("/admin/", HTTP_HOST="date.example")

        label, variant = _get_unfold_environment(request)

        with translation.override("en"):
            self.assertEqual(str(label), "Production")
        self.assertEqual(variant, "success")

    def test_registry_permission_strings_match_models(self):
        links = [link for group in SIDEBAR_NAVIGATION for link in group.items]

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


class UnfoldActionHierarchyTests(TestCase):
    def setUp(self):
        if not settings.USE_UNFOLD:
            self.skipTest("Unfold is disabled")
        self.user = get_user_model().objects.create_superuser(
            username="unfold-admin",
            password="pass",
            email="unfold@example.com",
        )
        self.client.force_login(self.user)

    @override_settings(LANGUAGE_CODE="en")
    def test_changelist_uses_labeled_contextual_add_action(self):
        response = self.client.get(reverse("admin:members_member_changelist"))

        self.assertContains(response, "Add member")
        self.assertContains(response, '<span>Search</span>', html=True)
        self.assertContains(response, "Search by name, username, email")
        self.assertTemplateUsed(response, "unfold/helpers/add_link.html")
        self.assertTemplateUsed(response, "admin/search_form.html")
        self.assertNotContains(response, "openQuickCreate")

    @override_settings(LANGUAGE_CODE="en")
    def test_dashboard_uses_explicit_model_actions(self):
        response = self.client.get(reverse("admin:index"))

        self.assertContains(response, "View all")
        self.assertContains(response, "Add")
        self.assertTemplateUsed(response, "unfold/helpers/app_list_default.html")

    @override_settings(LANGUAGE_CODE="en")
    def test_change_form_has_close_and_public_object_actions(self):
        from staticpages.models import StaticPage

        page = StaticPage.objects.create(slug="unfold-actions", members_only=False)
        response = self.client.get(reverse("admin:staticpages_staticpage_change", args=[page.pk]))

        self.assertContains(response, "Add another static page")
        self.assertContains(response, "Close")
        self.assertContains(response, "View on site")
        self.assertNotContains(response, "Open public page")


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

    def test_get_readonly_fields_places_public_url_only_in_classic_admin(self):
        from staticpages.models import StaticPage

        obj = StaticPage.objects.create(slug='test-ro', members_only=False)
        request = self.factory.get('/')
        readonly_fields = self.admin.get_readonly_fields(request, obj=obj)
        if settings.USE_UNFOLD:
            self.assertNotIn('public_url', readonly_fields)
        else:
            self.assertIn('public_url', readonly_fields)

    def test_get_readonly_fields_excludes_public_url_for_new_object(self):
        request = self.factory.get('/')
        self.assertNotIn('public_url', self.admin.get_readonly_fields(request, obj=None))


class UnfoldFormMixinTests(TestCase):
    def test_mixin_does_not_break_form_init(self):
        from django import forms

        class _SampleForm(UnfoldFormMixin, forms.Form):
            name = forms.CharField()
            password = forms.CharField(widget=forms.PasswordInput)
            url = forms.URLField()

        form = _SampleForm(data={'name': 'test', 'password': 'secret', 'url': 'https://example.com'})
        self.assertTrue(form.is_valid())
        if settings.USE_UNFOLD:
            self.assertIn('Toggle password visibility', form['password'].as_widget())

    def test_mixin_preserves_widget_attributes(self):
        from django import forms

        class _SampleForm(UnfoldFormMixin, forms.Form):
            value = forms.CharField(widget=forms.TextInput(attrs={'placeholder': 'Example', 'data-test': 'kept'}))

        widget = _SampleForm().fields['value'].widget

        self.assertEqual(widget.attrs['placeholder'], 'Example')
        self.assertEqual(widget.attrs['data-test'], 'kept')


class AdminFileWidgetTests(TestCase):
    def test_file_widget_renders_an_upload_control(self):
        rendered = SafeAdminFileWidget().render('file', None, {'id': 'id_file'})

        self.assertIn('type="file"', rendered)
        if settings.USE_UNFOLD:
            self.assertIn('file_upload', rendered)

    def test_multiple_file_widget_preserves_multiple_selection(self):
        rendered = SafeAdminMultipleFileWidget().render('files', None, {'id': 'id_files'})

        self.assertIn('type="file"', rendered)
        self.assertIn('multiple', rendered)

    def test_image_widget_keeps_unfold_image_template(self):
        rendered = SafeAdminImageWidget().render('image', None, {'id': 'id_image'})

        self.assertIn('type="file"', rendered)
        if settings.USE_UNFOLD:
            self.assertIn('>upload<', rendered)

    def test_public_multi_upload_forms_do_not_use_admin_markup(self):
        from exambank.forms import ExamArchiveAdminForm, ExamUploadForm
        from gallery.forms import AlbumAdminForm, AlbumUploadForm

        public_widgets = (AlbumUploadForm()['images'].as_widget(), ExamUploadForm()['exam'].as_widget())
        admin_widgets = (
            AlbumAdminForm()['images'].as_widget(),
            ExamArchiveAdminForm()['files'].as_widget(),
        )

        for widget in public_widgets:
            self.assertNotIn('file_upload', widget)
        if settings.USE_UNFOLD:
            for widget in admin_widgets:
                self.assertIn('file_upload', widget)
