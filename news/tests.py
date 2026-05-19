from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from members.models import Member
from news.models import Post


class NewsTestCase(TestCase):
    def setUp(self):
        self.member = Member.objects.create(username="Test", password="test", is_superuser=True)
        self.post = Post.objects.create(
            title="Test news",
            slug="test",
            author_id=self.member.id,
            published_time=timezone.now() - timezone.timedelta(seconds=1),
        )
        self.assertIsNotNone(self.post)
        self.assertTrue(self.post.published)
        self.assertIsInstance(self.post, Post)

    def test_unpublish_clears_published_time(self):
        self.post.unpublish()
        self.assertIsNone(self.post.published_time)
        self.assertFalse(self.post.published)

    def test_scheduled_post_is_not_listed(self):
        from django.utils import timezone

        self.post.published_time = timezone.now() + timezone.timedelta(days=1)
        self.post.save()
        response = self.client.get(reverse("news:index"))
        self.assertEqual(response.status_code, 200)
        self.assertNotIn(self.post, list(response.context["latest_news_items"]))

    def test_get_news_index(self):
        c = Client()
        response = c.get(reverse("news:index"))
        self.assertEqual(response.status_code, 200)

    def test_get_news_detail(self):
        c = Client()
        response = c.get(reverse("news:detail", args=[self.post.slug]))
        self.assertEqual(response.status_code, 200)
