from django.test import Client, TestCase
from django.urls import reverse

from members.models import Member
from news.models import Post


class NewsTestCase(TestCase):
    def setUp(self):
        self.member = Member.objects.create(username='Test', password='test', is_superuser=True)
        self.post = Post.objects.create(title='Test news', slug='test', author_id=self.member.id)
        self.assertIsNotNone(self.post)
        self.assertTrue(self.event.published)
        self.assertIsInstance(self.post, Post)

    def test_get_news_index(self):
        c = Client()
        response = c.get(reverse('news:index'))
        self.assertEqual(response.status_code, 200)

    def test_get_news_detail(self):
        c = Client()
        response = c.get(reverse('news:detail', args=[self.post.slug]))
        self.assertEqual(response.status_code, 200)

    def test_unpublished_news(self):
        c = Client()
        post = Post.objects.create(title='Test news', slug='test', author_id=self.member.id, published=False)
        response = c.get(reverse('news:detail', args=[post.slug]))
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.context.get('articles', None))


