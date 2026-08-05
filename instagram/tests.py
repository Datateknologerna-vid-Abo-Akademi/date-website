from unittest.mock import MagicMock, patch

from django.test import TestCase, override_settings

from instagram.models import IgUrl
from instagram.tasks import fetch_instagram_posts


def _mock_profile(posts):
    profile = MagicMock()
    profile.get_posts.return_value = iter(posts)
    return profile


class FetchInstagramPostsTests(TestCase):
    def test_replaces_existing_rows_on_success(self):
        IgUrl.objects.create(url="https://old.example/1.jpg", shortcode="old")
        posts = [
            MagicMock(url="https://img.example/1.jpg", shortcode="abc123"),
            MagicMock(url="https://img.example/2.jpg", shortcode="def456"),
        ]
        with patch("instagram.tasks.instaloader") as loader:
            loader.Profile.from_username.return_value = _mock_profile(posts)
            fetch_instagram_posts.run()

        stored = list(IgUrl.objects.order_by("id").values_list("url", "shortcode"))
        self.assertEqual(stored, [("https://img.example/1.jpg", "abc123"), ("https://img.example/2.jpg", "def456")])

    def test_keeps_existing_rows_on_fetch_error(self):
        IgUrl.objects.create(url="https://old.example/1.jpg", shortcode="old")
        with patch("instagram.tasks.instaloader") as loader:
            loader.Profile.from_username.side_effect = RuntimeError("Instagram blocked the request")
            with self.assertRaises(RuntimeError):
                fetch_instagram_posts.run()

        stored = list(IgUrl.objects.values_list("url", "shortcode"))
        self.assertEqual(stored, [("https://old.example/1.jpg", "old")])

    def test_keeps_existing_rows_when_fetch_returns_nothing(self):
        IgUrl.objects.create(url="https://old.example/1.jpg", shortcode="old")
        with patch("instagram.tasks.instaloader") as loader:
            loader.Profile.from_username.return_value = _mock_profile([])
            fetch_instagram_posts.run()

        stored = list(IgUrl.objects.values_list("url", "shortcode"))
        self.assertEqual(stored, [("https://old.example/1.jpg", "old")])

    def test_uses_configured_profile_and_credentials(self):
        with patch("instagram.tasks.instaloader") as loader:
            loader.Profile.from_username.return_value = _mock_profile([])
            with override_settings(
                INSTAGRAM_PROFILE="some_profile", INSTAGRAM_USERNAME="user", INSTAGRAM_PASSWORD="pass"
            ):
                fetch_instagram_posts.run()

        instance = loader.Instaloader()
        loader.Profile.from_username.assert_called_once_with(instance.context, "some_profile")
        instance.login.assert_called_once_with("user", "pass")

    def test_fetches_at_most_max_posts(self):
        many_posts = [MagicMock(url=f"https://img.example/{i}.jpg", shortcode=f"code{i}") for i in range(50)]
        with patch("instagram.tasks.instaloader") as loader:
            loader.Profile.from_username.return_value = _mock_profile(many_posts)
            fetch_instagram_posts.run()

        self.assertEqual(IgUrl.objects.count(), 40)
