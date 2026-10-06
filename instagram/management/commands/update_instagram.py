"""Replace the fetched Instagram posts with the latest posts from INSTAGRAM_USERNAME.

Posts with an uploaded image are managed in the admin and are left untouched.
"""

from itertools import islice

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from instagram.models import IgUrl

POST_LIMIT = 40


class Command(BaseCommand):
    help = "Replace the stored Instagram posts with the latest posts from this site's INSTAGRAM_USERNAME."

    def handle(self, *args, **options):
        username = settings.INSTAGRAM_USERNAME
        if not username:
            raise CommandError("INSTAGRAM_USERNAME is not set for this site.")

        try:
            import instaloader
        except ImportError as exc:
            raise CommandError("instaloader is not installed; run `uv sync --extra instagram`.") from exc

        loader = instaloader.Instaloader()
        try:
            profile = instaloader.Profile.from_username(loader.context, username)
            posts = [(post.url, post.shortcode) for post in islice(profile.get_posts(), POST_LIMIT)]
        except instaloader.InstaloaderException as exc:
            raise CommandError(f"Could not fetch posts for {username}; the stored posts were kept. {exc}") from exc

        if not posts:
            raise CommandError(f"{username} has no posts; the stored posts were kept.")

        with transaction.atomic():
            IgUrl.objects.filter(image="").delete()
            for url, shortcode in reversed(posts):
                IgUrl.objects.create(url=url, shortcode=shortcode)

        self.stdout.write(self.style.SUCCESS(f"Stored {len(posts)} posts from {username}."))
