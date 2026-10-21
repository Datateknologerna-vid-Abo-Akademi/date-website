import importlib
from unittest.mock import MagicMock, PropertyMock, patch

from django.conf import settings
from django.contrib.auth.models import AnonymousUser
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse
from django.utils import translation

from members.models import ORDINARY_MEMBER, Member, MembershipType
from staticpages.context_processors import get_categories, get_urls, navigation
from staticpages.models import StaticPage, StaticPageNav, StaticUrl


class PolicyViewTests(TestCase):
    @patch("staticpages.views.requests.get")
    def test_equality_plan_view_renders_remote_markdown(self, mock_get):
        mock_response = MagicMock()
        mock_response.text = "# Equality Plan\n\n- First point"
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        response = self.client.get(reverse("staticpages:equality_plan"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "<h1>Equality Plan</h1>", html=True)
        self.assertContains(response, "<li>First point</li>", html=True)

    def test_registration_terms_view_renders_local_document(self):
        response = self.client.get(reverse("staticpages:registration_terms"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Anmälningsvillkor gällande evenemang")
        self.assertContains(response, "Reservlista och ersättare")

    def test_registration_terms_view_renders_english(self):
        self.client.cookies[settings.LANGUAGE_COOKIE_NAME] = "en"
        response = self.client.get(reverse("staticpages:registration_terms"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "<h1>Event registration terms</h1>", html=True)
        self.assertContains(response, "Your registration becomes binding once the registration period has ended.")
        self.assertContains(response, "Waitlist and replacements")

    @override_settings(LANGUAGES=(("sv", "Svenska"), ("en", "English")))
    def test_registration_terms_view_falls_back_to_swedish_for_finnish_cookie(self):
        self.client.cookies[settings.LANGUAGE_COOKIE_NAME] = "fi"
        response = self.client.get(reverse("staticpages:registration_terms"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "<h1>Anmälningsvillkor gällande evenemang</h1>", html=True)
        self.assertContains(response, "Reservlista och ersättare")

    def test_registration_terms_view_renders_swedish_title(self):
        response = self.client.get(reverse("staticpages:registration_terms"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "<h1>Anmälningsvillkor gällande evenemang</h1>", html=True)

    @override_settings(EQUALITY_PLAN_ENABLED=False, REGISTRATION_TERMS_ENABLED=False)
    def test_policy_views_are_date_only(self):
        equality_response = self.client.get(reverse("staticpages:equality_plan"))
        terms_response = self.client.get(reverse("staticpages:registration_terms"))

        self.assertEqual(equality_response.status_code, 404)
        self.assertEqual(terms_response.status_code, 404)


class StaticPageViewTests(TestCase):
    def test_static_page_view_renders_background_image_url(self):
        StaticPage.objects.create(
            title="Background page",
            slug="background-page",
            content="<p>Visible content</p>",
            image="pages/background.jpg",
        )

        response = self.client.get(reverse("staticpages:page", args=["background-page"]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'background: url("/media/pages/background.jpg")')

    def test_static_page_view_ignores_unresolvable_background_image_url(self):
        StaticPage.objects.create(
            title="Broken background page",
            slug="broken-background-page",
            content="<p>Visible content</p>",
            image="pages/missing.jpg",
        )

        with patch(
            "django.db.models.fields.files.FieldFile.url",
            new_callable=PropertyMock,
            side_effect=ValueError("missing file"),
        ):
            response = self.client.get(reverse("staticpages:page", args=["broken-background-page"]))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "background: url(")
        self.assertContains(response, "Visible content")

    @override_settings(USE_S3=True)
    def test_static_page_background_image_url_prefers_s3_in_s3_mode(self):
        page = StaticPage(
            title="S3 page",
            slug="s3-page",
            image="pages/private.jpg",
            s3_image="pages/public.jpg",
        )

        self.assertEqual(page.background_image_url, "/media/pages/public.jpg")

    def test_static_page_rejects_local_and_s3_background_images_together(self):
        page = StaticPage(
            title="Invalid page",
            slug="invalid-page",
            image="pages/private.jpg",
            s3_image="pages/public.jpg",
        )

        with self.assertRaises(ValidationError) as error:
            page.full_clean()

        self.assertIn("image", error.exception.message_dict)
        self.assertIn("s3_image", error.exception.message_dict)


class StaticPageContentStylingTests(TestCase):
    """CKEditor writes image alignment as classes on the rendered HTML.

    Those classes only do something when the public page links the matching
    stylesheet and marks the wrapper with `ck-content`, so both halves are
    asserted here. Without them an image renders as a plain block figure
    whatever alignment the editor showed.
    """

    def setUp(self):
        self.page = StaticPage.objects.create(title="Styling", slug="styling", content="<p>Text</p>")
        self.url = reverse("staticpages:page", args=[self.page.slug])

    def test_rendered_content_is_marked_as_ckeditor_content(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'class="content ck-content"')

    def test_page_links_the_ckeditor_content_stylesheet(self):
        response = self.client.get(self.url)

        self.assertContains(response, "core/css/ck-content.css")


class PulteritStaticPageStylingTests(TestCase):
    """pulterit replaces the extra_head block to add its own background image.

    A child block that does not call `block.super` silently drops the parent's
    stylesheets, which is how the CKEditor content styles went missing there.
    """

    def test_pulterit_page_keeps_the_shared_content_stylesheets(self):
        pulterit_settings = importlib.import_module("core.settings.pulterit")
        page = StaticPage.objects.create(title="Styling", slug="styling-pulterit", content="<p>Text</p>")

        with override_settings(
            PROJECT_NAME="pulterit",
            TEMPLATES=pulterit_settings.TEMPLATES,
            STATICFILES_DIRS=pulterit_settings.STATICFILES_DIRS,
        ):
            response = self.client.get(reverse("staticpages:page", args=[page.slug]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "staticpages/css/staticpage.css")
        self.assertContains(response, "core/css/ck-content.css")


class StaticUrlTests(TestCase):
    def setUp(self):
        self.category = StaticPageNav.objects.create(category_name="Menu")
        # The navigation cache is process-wide; isolate tests from entries
        # created by earlier tests in the same run.
        cache.clear()

    def test_blank_leaf_url_is_allowed_for_draft_menu_items(self):
        nav_url = StaticUrl(title="Empty", category=self.category, url="")

        nav_url.full_clean()

    def test_blank_parent_url_is_valid_when_it_has_children(self):
        parent = StaticUrl.objects.create(title="Parent", category=self.category, url="")
        StaticUrl.objects.create(title="Child", category=self.category, parent=parent, url="/child/")

        parent.full_clean()

    def test_child_urls_must_stay_one_level_deep(self):
        parent = StaticUrl.objects.create(title="Parent", category=self.category, url="/parent/")
        child = StaticUrl.objects.create(title="Child", category=self.category, parent=parent, url="/child/")
        grandchild = StaticUrl(title="Grandchild", category=self.category, parent=child, url="/grandchild/")

        with self.assertRaises(ValidationError) as error:
            grandchild.full_clean()

        self.assertIn("parent", error.exception.message_dict)

    def test_context_processor_filters_archive_children_when_archive_is_disabled(self):
        request = RequestFactory().get("/")
        request.user = AnonymousUser()
        parent = StaticUrl.objects.create(title="Parent", category=self.category, url="/parent/")
        StaticUrl.objects.create(title="Archive child", category=self.category, parent=parent, url="/archive/old/")
        StaticUrl.objects.create(title="Visible child", category=self.category, parent=parent, url="/current/")

        with override_settings(ARCHIVE_ENABLED=False):
            urls = get_urls(request)["urls"]
            children = list(urls[0].children.all())

        self.assertEqual([child.title for child in children], ["Visible child"])

    def test_context_processor_keeps_exambank_urls_when_archive_is_disabled(self):
        request = RequestFactory().get("/")
        request.user = AnonymousUser()
        parent = StaticUrl.objects.create(title="Parent", category=self.category, url="/parent/")
        StaticUrl.objects.create(title="Exam child", category=self.category, parent=parent, url="/archive/exams/")
        StaticUrl.objects.create(
            title="Exam detail child", category=self.category, parent=parent, url="/archive/exams/1/"
        )
        StaticUrl.objects.create(title="Archive child", category=self.category, parent=parent, url="/archive/old/")
        StaticUrl.objects.create(
            title="Examined files", category=self.category, parent=parent, url="/archive/examined/"
        )

        installed_with_exambank = list(settings.INSTALLED_APPS)
        if 'exambank' not in installed_with_exambank:
            installed_with_exambank.append('exambank')

        with (
            override_settings(ARCHIVE_ENABLED=False),
            patch.object(settings, 'INSTALLED_APPS', new=installed_with_exambank),
        ):
            urls = get_urls(request)["urls"]
            children = list(urls[0].children.all())

        self.assertEqual(
            sorted(child.title for child in children),
            ["Exam child", "Exam detail child"],
        )

    def test_context_processor_hides_all_archive_urls_when_exambank_not_installed(self):
        request = RequestFactory().get("/")
        request.user = AnonymousUser()
        parent = StaticUrl.objects.create(title="Parent", category=self.category, url="/parent/")
        StaticUrl.objects.create(title="Exam child", category=self.category, parent=parent, url="/archive/exams/")
        StaticUrl.objects.create(title="Visible child", category=self.category, parent=parent, url="/current/")

        installed_without_exambank = [app for app in settings.INSTALLED_APPS if app != 'exambank']

        with (
            override_settings(ARCHIVE_ENABLED=False),
            patch.object(settings, 'INSTALLED_APPS', new=installed_without_exambank),
        ):
            urls = get_urls(request)["urls"]
            children = list(urls[0].children.all())

        self.assertEqual([child.title for child in children], ["Visible child"])

    def test_get_categories_keeps_exambank_category_when_archive_is_disabled(self):
        request = RequestFactory().get("/")
        request.user = AnonymousUser()
        exam_category = StaticPageNav.objects.create(
            category_name="Exams",
            nav_element=10,
            use_category_url=True,
            url="/archive/exams/",
        )
        StaticPageNav.objects.create(
            category_name="Archive",
            nav_element=20,
            use_category_url=True,
            url="/archive/old/",
        )

        installed_with_exambank = list(settings.INSTALLED_APPS)
        if 'exambank' not in installed_with_exambank:
            installed_with_exambank.append('exambank')

        with (
            override_settings(ARCHIVE_ENABLED=False),
            patch.object(settings, 'INSTALLED_APPS', new=installed_with_exambank),
        ):
            categories = get_categories(request)["categories"]

        self.assertIn(exam_category, categories)
        self.assertFalse(any(category.url == "/archive/old/" for category in categories))

    def test_context_processor_filters_logged_in_only_children_for_anonymous_users(self):
        request = RequestFactory().get("/")
        request.user = AnonymousUser()
        parent = StaticUrl.objects.create(title="Parent", category=self.category, url="/parent/")
        StaticUrl.objects.create(
            title="Hidden child",
            category=self.category,
            parent=parent,
            url="/hidden/",
            logged_in_only=True,
        )
        StaticUrl.objects.create(title="Visible child", category=self.category, parent=parent, url="/current/")

        urls = get_urls(request)["urls"]
        children = list(urls[0].children.all())

        self.assertEqual([child.title for child in children], ["Visible child"])


class StaticPageAdminTests(TestCase):
    def setUp(self):
        self.admin_user = Member.objects.create_superuser(
            username="staticpages-admin",
            password="pwd",
            email="staticpages-admin@example.com",
            membership_type=MembershipType.objects.get(pk=ORDINARY_MEMBER),
        )
        self.category = StaticPageNav.objects.create(category_name="Menu")
        self.client.force_login(self.admin_user)

    def test_nav_link_form_autocompletes_the_sites_own_pages(self):
        StaticPage.objects.create(title="Om oss", slug="om-oss")
        StaticUrl.objects.create(title="Om oss", category=self.category, url="/pages/om-oss/")

        response = self.client.get(reverse("admin:staticpages_staticpagenav_change", args=[self.category.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name="staticurl_set-0-url"')
        self.assertContains(response, 'list="id_staticurl_set-0-url_suggestions"')
        self.assertContains(response, "<datalist")
        self.assertContains(response, "/pages/om-oss/")

    def test_static_page_form_shows_only_the_storage_specific_background_image(self):
        page = StaticPage.objects.create(title="Bakgrund", slug="bakgrund")

        response = self.client.get(reverse("admin:staticpages_staticpage_change", args=[page.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name="image"')
        self.assertNotContains(response, 'name="s3_image"')
        self.assertContains(response, "Bakgrundsbild (lokal)")

    @override_settings(USE_S3=True)
    def test_static_page_form_shows_the_public_s3_image_when_s3_is_enabled(self):
        page = StaticPage.objects.create(title="S3-bakgrund", slug="s3-bakgrund")

        response = self.client.get(reverse("admin:staticpages_staticpage_change", args=[page.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name="s3_image"')
        self.assertNotContains(response, 'name="image"')
        self.assertContains(response, "Bakgrundsbild (publik S3)")

    def test_static_page_form_keeps_a_stale_image_from_the_other_storage(self):
        page = StaticPage.objects.create(title="Gammal bild", slug="gammal-bild", s3_image="pages/old.jpg")

        response = self.client.get(reverse("admin:staticpages_staticpage_change", args=[page.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name="image"')
        self.assertContains(response, 'name="s3_image"')

    def test_category_url_is_ignored_when_use_category_url_is_off(self):
        category = StaticPageNav(category_name="Meny", use_category_url=False, url="pages/legacy/")

        category.full_clean()

    def test_nav_link_rejects_a_relative_url_without_a_leading_slash(self):
        nav_url = StaticUrl(title="Typo", category=self.category, url="pages/om-oss/")

        with self.assertRaises(ValidationError) as error:
            nav_url.full_clean()

        self.assertIn("url", error.exception.message_dict)

    def test_nav_link_accepts_external_and_root_relative_urls(self):
        for url in ("https://example.com/", "mailto:info@example.com", "/pages/om-oss/", "#top"):
            with self.subTest(url=url):
                StaticUrl(title="Link", category=self.category, url=url).full_clean()

    def test_category_url_is_required_when_use_category_url_is_checked(self):
        category = StaticPageNav(category_name="Direct", use_category_url=True, url="")

        with self.assertRaises(ValidationError) as error:
            category.full_clean()

        self.assertIn("url", error.exception.message_dict)

    def test_static_page_form_shows_where_the_page_is_linked(self):
        page = StaticPage.objects.create(title="Om oss", slug="om-oss")
        StaticUrl.objects.create(title="Om oss", category=self.category, url=page.get_absolute_url())

        response = self.client.get(reverse("admin:staticpages_staticpage_change", args=[page.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Länkad i menyn")
        self.assertContains(
            response,
            reverse("admin:staticpages_staticpagenav_change", args=[self.category.pk]),
        )

    def test_static_page_form_reports_a_page_that_is_not_in_the_menu(self):
        page = StaticPage.objects.create(title="Ny sida", slug="ny-sida")

        response = self.client.get(reverse("admin:staticpages_staticpage_change", args=[page.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Sidan finns inte i menyn.")


class NavigationProcessorTests(TestCase):
    """The merged navigation processor: one load, cached for anonymous
    visitors, invalidated on admin edits, off in development."""

    def setUp(self):
        self.request = RequestFactory().get("/")
        self.request.user = AnonymousUser()
        self.category = StaticPageNav.objects.create(category_name="Main", nav_element=1)
        self.url = StaticUrl.objects.create(title="Home", category=self.category, url="/", dropdown_element=1)
        cache.clear()

    def test_navigation_returns_categories_and_urls_in_one_load(self):
        with self.assertNumQueries(3):
            context = navigation(self.request)
        self.assertEqual([u.title for u in context["urls"]], ["Home"])
        self.assertEqual([c.category_name for c in context["categories"]], ["Main"])

    def test_anonymous_navigation_is_cached(self):
        navigation(self.request)
        with self.assertNumQueries(0):
            navigation(self.request)

    def test_admin_edit_invalidates_the_cache(self):
        navigation(self.request)
        with self.captureOnCommitCallbacks(execute=True):
            self.url.title = "Front page"
            self.url.save()
        with self.assertNumQueries(3):
            context = navigation(self.request)
        self.assertEqual([u.title for u in context["urls"]], ["Front page"])

    def test_cache_key_is_isolated_by_language(self):
        navigation(self.request)
        with self.captureOnCommitCallbacks(execute=True):
            pass
        # A different active language must not reuse the Swedish entry.
        with translation.override("fi"):
            with self.assertNumQueries(3):
                navigation(self.request)

    def test_logged_in_users_are_not_cached(self):
        self.request.user = MagicMock()
        self.request.user.is_authenticated = True
        with self.assertNumQueries(3):
            navigation(self.request)
        with self.assertNumQueries(3):
            navigation(self.request)
