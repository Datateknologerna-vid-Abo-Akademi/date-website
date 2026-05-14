from unittest.mock import MagicMock, PropertyMock, patch

from django.conf import settings
from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import ValidationError
from django.test import RequestFactory
from django.test import TestCase, override_settings
from django.urls import reverse

from staticpages.context_processors import get_urls
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

    @override_settings(PROJECT_NAME="kk")
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


class StaticUrlTests(TestCase):
    def setUp(self):
        self.category = StaticPageNav.objects.create(category_name="Menu")

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
        StaticUrl.objects.create(title="Archive child", category=self.category, parent=parent, url="/archive/old/")

        with override_settings(ARCHIVE_ENABLED=False):
            urls = get_urls(request)["urls"]
            children = list(urls[0].children.all())

        self.assertEqual([child.title for child in children], ["Exam child"])

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
