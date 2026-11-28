"""Open Graph and Twitter Card tags on public pages.

The image URL needs ``absolute_uri`` because one association's media may live on
local disk while another serves it from S3 or a CDN, where the storage already
returns an absolute URL. Prefixing the request host to that URL points at a page
on this site instead of at the file, and the crawler then finds no image.
"""

import re
from datetime import timedelta
from unittest.mock import PropertyMock, patch

from django.test import RequestFactory, SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from date.templatetags.og_tags import absolute_uri, plaintext_truncate
from members.models import Member
from news.models import Post
from staticpages.models import StaticPage

CDN_IMAGE = "https://cdn.example.org/media/pages/background.jpg"


def flatten(html):
    """The templates wrap long meta tags, so match on the flattened page."""
    return re.sub(r"\s+", " ", html)


class AbsoluteUriTests(SimpleTestCase):
    def setUp(self):
        self.request = RequestFactory().get("/")

    def test_relative_path_gets_the_request_host(self):
        self.assertEqual(absolute_uri("/media/pages/x.jpg", self.request), "http://testserver/media/pages/x.jpg")

    def test_absolute_url_is_left_alone(self):
        self.assertEqual(absolute_uri(CDN_IMAGE, self.request), CDN_IMAGE)

    def test_missing_request_returns_the_value_unchanged(self):
        self.assertEqual(absolute_uri("/media/pages/x.jpg", None), "/media/pages/x.jpg")

    def test_empty_value(self):
        self.assertEqual(absolute_uri("", self.request), "")
        self.assertEqual(absolute_uri(None, self.request), "")


class PlaintextTruncateTests(SimpleTestCase):
    def test_removes_html_and_collapses_whitespace(self):
        self.assertEqual(plaintext_truncate("<p>Hej  <b>världen</b></p>"), "Hej världen")

    def test_truncates_to_the_limit(self):
        self.assertEqual(plaintext_truncate("a" * 300, 10), "a" * 10 + "...")

    def test_shorter_text_is_untouched(self):
        self.assertEqual(plaintext_truncate("<p>Kort</p>", 160), "Kort")

    def test_empty_value(self):
        self.assertEqual(plaintext_truncate(""), "")
        self.assertEqual(plaintext_truncate(None), "")


class OgMetaRenderTests(TestCase):
    @override_settings(USE_S3=True)
    def test_static_page_keeps_an_already_absolute_image_url(self):
        StaticPage.objects.create(
            title="Background page",
            slug="og-background-page",
            content="<p>Visible content</p>",
            image="pages/background.jpg",
        )
        with patch(
            "django.db.models.fields.files.FieldFile.url",
            new_callable=PropertyMock,
            return_value=CDN_IMAGE,
        ):
            response = self.client.get(reverse("staticpages:page", args=["og-background-page"]))

        self.assertEqual(response.status_code, 200)
        html = flatten(response.content.decode())
        self.assertIn(f'<meta property="og:image" content="{CDN_IMAGE}">', html)
        self.assertIn(f'<meta name="twitter:image" content="{CDN_IMAGE}">', html)
        # The bug this guards against: the request host in front of an absolute file URL.
        self.assertNotIn(f"http://testserver/{CDN_IMAGE}", html)
        self.assertIn('<meta property="og:title" content="Background page">', html)
        self.assertIn('<meta property="og:description" content="Visible content">', html)
        self.assertIn('<meta name="twitter:card" content="summary_large_image">', html)

    def test_static_page_without_image_uses_the_summary_card(self):
        StaticPage.objects.create(title="Plain page", slug="og-plain-page", content="<p>Body</p>")
        response = self.client.get(reverse("staticpages:page", args=["og-plain-page"]))

        html = flatten(response.content.decode())
        self.assertIn('<meta name="twitter:card" content="summary">', html)
        self.assertNotIn("og:image", html)

    def test_static_page_relative_image_becomes_absolute(self):
        StaticPage.objects.create(
            title="Relative page",
            slug="og-relative-page",
            content="<p>Body</p>",
            image="pages/relative.jpg",
        )
        response = self.client.get(reverse("staticpages:page", args=["og-relative-page"]))

        html = flatten(response.content.decode())
        self.assertIn('content="http://testserver/media/pages/relative.jpg"', html)

    def test_news_article_carries_its_own_title_and_description(self):
        member = Member.objects.create(username="og-author", password="test")
        post = Post.objects.create(
            title="Nyhet",
            slug="og-nyhet",
            content="<p>Ett meddelande som handlar om saker.</p>",
            author_id=member.id,
            published_time=timezone.now() - timedelta(seconds=1),
        )
        response = self.client.get(post.get_absolute_url())

        self.assertEqual(response.status_code, 200)
        html = flatten(response.content.decode())
        self.assertIn('<meta property="og:title" content="Nyhet">', html)
        self.assertIn('<meta property="og:description" content="Ett meddelande som handlar om saker.">', html)
        self.assertIn('<meta name="twitter:title" content="Nyhet">', html)

    def test_page_without_an_og_meta_override_gets_the_association_default(self):
        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertIn('<meta property="og:title" content="Datateknologerna">', flatten(response.content.decode()))

    def test_og_tags_are_inside_the_document_head(self):
        StaticPage.objects.create(title="Head page", slug="og-head-page", content="<p>Body</p>")
        response = self.client.get(reverse("staticpages:page", args=["og-head-page"]))

        head = response.content.decode().split("</head>", 1)[0]
        self.assertIn('property="og:title"', head)
        self.assertIn('name="twitter:card"', head)
