from django.test import SimpleTestCase

from ctf.models import Ctf, Flag
from events.models import Event
from news.models import Category, Post
from publications.models import PDFFile
from staticpages.models import StaticPage


class SlugAbsoluteUrlTests(SimpleTestCase):
    def test_event_uses_slug_detail_url(self):
        self.assertEqual(Event(slug="spring-ball").get_absolute_url(), "/events/spring-ball/")

    def test_static_page_uses_slug_page_url(self):
        self.assertEqual(StaticPage(slug="about").get_absolute_url(), "/pages/about/")

    def test_news_post_without_category_uses_article_url(self):
        self.assertEqual(Post(slug="hello").get_absolute_url(), "/news/articles/hello/")

    def test_news_post_with_category_uses_category_article_url(self):
        category = Category(id=1, name="Updates", slug="updates")
        post = Post(slug="hello", category=category)
        self.assertEqual(post.get_absolute_url(), "/news/updates/hello/")

    def test_other_slugged_content_urls(self):
        ctf = Ctf(title="Puzzle Hunt", slug="puzzle-hunt")

        self.assertEqual(Category(slug="updates").get_absolute_url(), "/news/updates/")
        self.assertEqual(ctf.get_absolute_url(), "/ctf/puzzle-hunt")
        self.assertEqual(Flag(ctf=ctf, slug="first-flag").get_absolute_url(), "/ctf/puzzle-hunt/first-flag")
        self.assertEqual(PDFFile(title="Guide", slug="guide").get_absolute_url(), "/publications/guide/")
