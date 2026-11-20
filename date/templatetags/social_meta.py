"""Explicit image metadata for link previews on social platforms.

The title and description are deliberately not emitted: every platform falls
back to the page's own ``<title>`` and meta description, which are already the
per-page values, while a Django block cannot hand its rendered content to a
second tag. Only the image is set here, because a crawler otherwise picks
whatever it finds on the page (usually the footer logo, an SVG most of them
cannot render) or falls back to the favicon.

Each association ships its own image at ``static/<association>/core/images/``.
The static finders resolve the association copy before ``static/common``, so
the paths below stay association-neutral; ``static/common`` holds the DaTe
files that ``date`` and any new variant fall back to. Sizes and the per-page
override are documented in ``docs/dev/templates.md``.
"""

from django import template
from django.conf import settings
from django.templatetags.static import static
from django.utils.translation import gettext

register = template.Library()

SHARE_IMAGE = 'core/images/social-share.png'
APPLE_TOUCH_ICON = 'core/images/apple-touch-icon.png'
SHARE_IMAGE_WIDTH = 1200
SHARE_IMAGE_HEIGHT = 630
APPLE_TOUCH_ICON_SIZE = 180


def _absolute_static(path, request):
    """Return an absolute URL for a static file.

    Manifest storage returns a hashed path and an S3-backed static storage
    returns an absolute URL already; only a site-relative path needs the
    request (or ``SITE_URL`` when a template renders outside a request).
    """
    url = static(path)
    if url.startswith(('http://', 'https://', '//')):
        return url
    if request is not None:
        return request.build_absolute_uri(url)
    site_url = str(settings.CONTENT_VARIABLES.get('SITE_URL', '') or '').rstrip('/')
    return f'{site_url}{url}'


@register.inclusion_tag('core/social_meta.html', takes_context=True)
def social_meta(context):
    """Render the share image, card type, site name and canonical URL."""
    request = context.get('request')
    association_name = settings.CONTENT_VARIABLES.get('ASSOCIATION_NAME', '')
    association_name_full = settings.CONTENT_VARIABLES.get('ASSOCIATION_NAME_FULL', association_name)
    # Reuses the "%(association_name)s logo" catalogue entry the footer already has.
    image_alt = gettext('%(association_name)s logo') % {'association_name': association_name_full}
    return {
        'association_name': association_name,
        'canonical_url': request.build_absolute_uri(request.path) if request is not None else '',
        'share_image': _absolute_static(SHARE_IMAGE, request),
        'share_image_alt': image_alt,
        'share_image_width': SHARE_IMAGE_WIDTH,
        'share_image_height': SHARE_IMAGE_HEIGHT,
        'apple_touch_icon': _absolute_static(APPLE_TOUCH_ICON, request),
        'apple_touch_icon_size': APPLE_TOUCH_ICON_SIZE,
    }
