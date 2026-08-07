import unittest
from unittest.mock import patch

from django.conf import settings
from django.test import TestCase
from django.urls import reverse

if "klotterplanket" not in settings.INSTALLED_APPS:
    raise unittest.SkipTest("klotterplanket app is not installed in this settings module")

from .models import Post  # noqa: E402


class KlotterplanketViewTests(TestCase):
    def test_index_get_renders_empty_state(self):
        response = self.client.get(reverse('klotterplanket:index'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Inga inlägg ännu')

    def test_index_lists_posts_newest_first(self):
        first = Post.objects.create(pseudonym='Anka', content='Första inlägget')
        second = Post.objects.create(pseudonym='Musse', content='Andra inlägget')
        response = self.client.get(reverse('klotterplanket:index'))
        self.assertContains(response, 'Första inlägget')
        self.assertContains(response, 'Andra inlägget')
        self.assertEqual(list(response.context['posts']), [second, first])

    @patch('klotterplanket.views.validate_captcha', return_value=True)
    def test_valid_post_creates_post(self, mock_validate_captcha):
        response = self.client.post(
            reverse('klotterplanket:index'),
            {'pseudonym': 'Anka', 'content': 'Hej på er!', 'cf-turnstile-response': 'token'},
        )
        self.assertRedirects(response, reverse('klotterplanket:index'))
        self.assertEqual(Post.objects.count(), 1)
        post = Post.objects.get()
        self.assertEqual(post.pseudonym, 'Anka')
        self.assertEqual(post.content, 'Hej på er!')
        mock_validate_captcha.assert_called_once_with('token')

    @patch('klotterplanket.views.validate_captcha', return_value=False)
    def test_post_with_failed_captcha_is_rejected(self, mock_validate_captcha):
        response = self.client.post(
            reverse('klotterplanket:index'),
            {'pseudonym': 'Anka', 'content': 'Hej på er!', 'cf-turnstile-response': 'token'},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Post.objects.count(), 0)
        mock_validate_captcha.assert_called_once_with('token')
        self.assertContains(response, 'Botkontrollen misslyckades')
        self.assertEqual(response.context['form']['pseudonym'].value(), 'Anka')

    def test_post_without_captcha_token_is_rejected(self):
        with self.settings(TURNSTILE_SECRET_KEY='test'):
            response = self.client.post(
                reverse('klotterplanket:index'),
                {'pseudonym': 'Anka', 'content': 'Hej på er!'},
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Post.objects.count(), 0)

    def test_invalid_form_is_rejected(self):
        response = self.client.post(
            reverse('klotterplanket:index'),
            {'pseudonym': '', 'content': ''},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Post.objects.count(), 0)
        self.assertContains(response, 'Kontrollera pseudonymen och meddelandet.')
        self.assertFalse(response.context['form'].is_valid())

    def test_content_length_limit_is_enforced(self):
        response = self.client.post(
            reverse('klotterplanket:index'),
            {'pseudonym': 'Anka', 'content': 'x' * 1001},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Post.objects.count(), 0)
        self.assertFalse(response.context['form'].is_valid())
