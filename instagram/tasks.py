import logging
from itertools import islice

import instaloader
from celery import shared_task
from django.conf import settings
from django.db import transaction

from instagram.models import IgUrl

logger = logging.getLogger("date")

MAX_POSTS = 40


def _fetch_instagram_posts(profile, username="", password=""):
    """Fetch the latest post URLs for a profile via instaloader.

    Returns a list of (url, shortcode) tuples. Raises on any fetch error so
    the caller can decide whether existing rows are safe to replace.
    """
    loader = instaloader.Instaloader()
    if username and password:
        loader.login(username, password)
    ig_profile = instaloader.Profile.from_username(loader.context, profile)
    return [(post.url, post.shortcode) for post in islice(ig_profile.get_posts(), MAX_POSTS)]


@shared_task
def fetch_instagram_posts():
    """Refresh the stored Instagram post URLs.

    Existing rows are only replaced when the fetch succeeds, so a transient
    Instagram error never wipes the home page feed.
    """
    posts = _fetch_instagram_posts(
        settings.INSTAGRAM_PROFILE,
        username=settings.INSTAGRAM_USERNAME,
        password=settings.INSTAGRAM_PASSWORD,
    )
    if not posts:
        logger.warning("Instagram fetch returned no posts for %s; keeping existing rows", settings.INSTAGRAM_PROFILE)
        return
    with transaction.atomic():
        IgUrl.objects.all().delete()
        IgUrl.objects.bulk_create([IgUrl(url=url, shortcode=shortcode) for url, shortcode in posts])
    logger.info("Refreshed %d Instagram posts for %s", len(posts), settings.INSTAGRAM_PROFILE)
