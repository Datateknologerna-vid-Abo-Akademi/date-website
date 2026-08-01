from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from members.models import Member
from news.models import Post


class NewsTestCase(TestCase):
    def setUp(self):
        self.member = Member.objects.create(username='Test', password='test', is_superuser=True)
        self.post = Post.objects.create(
            title='Test news',
            slug='test',
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
        response = self.client.get(reverse('news:index'))
        self.assertEqual(response.status_code, 200)
        self.assertNotIn(self.post, list(response.context['latest_news_items']))

    def test_get_news_index(self):
        c = Client()
        response = c.get(reverse('news:index'))
        self.assertEqual(response.status_code, 200)

    def test_get_news_detail(self):
        c = Client()
        response = c.get(reverse('news:detail', args=[self.post.slug]))
        self.assertEqual(response.status_code, 200)

    def test_index_orders_equal_publication_times_by_descending_pk(self):
        self.post.unpublish()
        published_time = timezone.now() - timezone.timedelta(minutes=1)
        posts = Post.objects.bulk_create(
            [
                Post(
                    title=f'Post {number}',
                    slug=f'post-{number}',
                    author=self.member,
                    published_time=published_time,
                )
                for number in range(11)
            ]
        )

        response = self.client.get(reverse('news:index'))

        listed_posts = list(response.context['latest_news_items'])
        self.assertEqual(listed_posts, list(reversed(posts))[:10])

    def test_index_renders_windowed_pagination(self):
        published_time = timezone.now() - timezone.timedelta(minutes=1)
        Post.objects.bulk_create(
            [
                Post(
                    title=f'Pagination post {number}',
                    slug=f'pagination-post-{number}',
                    author=self.member,
                    published_time=published_time,
                )
                for number in range(90)
            ]
        )

        response = self.client.get(reverse('news:index'), {'page': 5})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['latest_news_items'].number, 5)
        self.assertContains(response, '<a href="?page=1">1</a>', html=True)
        self.assertContains(response, '<a class="disabled">…</a>', count=2, html=True)
        for page_number in range(3, 8):
            if page_number == 5:
                self.assertContains(response, '<a class="active">5</a>', html=True)
            else:
                self.assertContains(response, f'<a href="?page={page_number}">{page_number}</a>', html=True)
        self.assertContains(response, '<a href="?page=10">10</a>', html=True)


class PageWindowTestCase(TestCase):
    def test_page_window(self):
        from news.views import _page_window

        cases = [
            # (current, total, window, expected dict)
            (
                1,
                1,
                2,
                {
                    'page_range_window': range(1, 2),
                    'show_first_page': False,
                    'show_last_page': False,
                    'show_first_ellipsis': False,
                    'show_last_ellipsis': False,
                },
            ),
            (
                1,
                5,
                2,
                {
                    'page_range_window': range(1, 4),
                    'show_first_page': False,
                    'show_last_page': True,
                    'show_first_ellipsis': False,
                    'show_last_ellipsis': True,
                },
            ),
            (
                2,
                5,
                2,
                {
                    'page_range_window': range(1, 5),
                    'show_first_page': False,
                    'show_last_page': True,
                    'show_first_ellipsis': False,
                    'show_last_ellipsis': False,
                },
            ),
            (
                3,
                5,
                2,
                {
                    'page_range_window': range(1, 6),
                    'show_first_page': False,
                    'show_last_page': False,
                    'show_first_ellipsis': False,
                    'show_last_ellipsis': False,
                },
            ),
            (
                4,
                5,
                2,
                {
                    'page_range_window': range(2, 6),
                    'show_first_page': True,
                    'show_last_page': False,
                    'show_first_ellipsis': False,
                    'show_last_ellipsis': False,
                },
            ),
            (
                5,
                5,
                2,
                {
                    'page_range_window': range(3, 6),
                    'show_first_page': True,
                    'show_last_page': False,
                    'show_first_ellipsis': True,
                    'show_last_ellipsis': False,
                },
            ),
            (
                5,
                20,
                2,
                {
                    'page_range_window': range(3, 8),
                    'show_first_page': True,
                    'show_last_page': True,
                    'show_first_ellipsis': True,
                    'show_last_ellipsis': True,
                },
            ),
            (
                3,
                5,
                0,
                {
                    'page_range_window': range(3, 4),
                    'show_first_page': True,
                    'show_last_page': True,
                    'show_first_ellipsis': True,
                    'show_last_ellipsis': True,
                },
            ),
        ]

        for current, total, window, expected in cases:
            with self.subTest(current=current, total=total, window=window):
                page_obj = _fake_page(current, total)
                result = _page_window(page_obj, window=window)
                self.assertEqual(result, expected)


def _fake_page(number, total):
    paginator = type('FakePaginator', (), {'num_pages': total})()
    return type('FakePage', (), {'number': number, 'paginator': paginator})()
