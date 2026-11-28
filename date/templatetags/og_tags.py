import re

from django import template
from django.utils.html import strip_tags

register = template.Library()


@register.filter
def absolute_uri(value, request=None):
    """Return an absolute URL for a media or static URL.

    A file backed by S3 or a CDN already returns an absolute URL, and prefixing
    it with the request scheme and host would produce a URL to a page on this
    site instead of to the file. ``build_absolute_uri`` keeps an absolute URL as
    it is and only joins a site-relative path to the request's host. Without a
    request (a template rendered outside a request) there is no host to join to,
    so the value is returned unchanged.
    """
    if not value:
        return ""
    if request is None:
        return value
    return request.build_absolute_uri(str(value))


@register.filter
def plaintext_truncate(value, arg=160):
    try:
        max_length = int(arg)
    except Exception:
        max_length = 160

    if not value:
        return ""

    text = strip_tags(value)
    text = re.sub(r"\s+", " ", text)
    text = text.strip()

    if len(text) > max_length:
        text = text[:max_length] + "..."

    return text
