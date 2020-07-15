from django.utils import timezone
from django.utils.text import slugify


def slugify_max(text, max_length=50):
    slug = slugify(text)
    if len(slug) <= max_length:
        return slug
    trimmed_slug = slug[:max_length].rsplit('-', 1)[0]
    if len(trimmed_slug) <= max_length:
        return trimmed_slug
    # First word is > max_length chars, so we have to break it
    return slug[:max_length]


def days_hence(days):
    return timezone.now() + timezone.timedelta(days=days)
