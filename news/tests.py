from django.test import Client, TestCase
from django.urls import reverse

from members.models import Member
from news.models import Post


class NewsTestCase(TestCase):
    def setUp(self):
        self.member = Member.objects.create(username='Test', password='test', is_superuser=True)
        self.post = Post.objects.create(title='Test news', slug='test', author_id=self.member.id)
        self.assertIsNotNone(self.post)
        self.assertTrue(self.post.published)
        self.assertIsInstance(self.post, Post)

    def test_get_news_index(self):
        c = Client()
        response = c.get(reverse('news:index'))
        self.assertEqual(response.status_code, 200)

    def test_get_news_detail(self):
        c = Client()
        response = c.get(reverse('news:detail', args=[self.post.slug]))
        self.assertEqual(response.status_code, 200)

    # Get not defined for news view, Client.get() will return error for unpublished article
    # def test_unpublished_news(self):
    #     c = Client(enforce_csrf_checks=False)
    #     post = Post.objects.create(title='Test news2', slug='test2', author_id=self.member.id, published=False)
    #     response = c.get(reverse('news:detail', args=[post.slug]))
    #     self.assertEqual(response.status_code, 404)
    #     self.assertIsNone(response.context.get('articles', None))


