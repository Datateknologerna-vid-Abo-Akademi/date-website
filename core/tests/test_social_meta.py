"""Every association ships an explicit image for link previews.

A shared link used to carry no open graph image at all, so the crawler picked
whatever it found on the page or the platform fell back to the favicon. These
tests pin the tag output and the per-association files it depends on: a variant
that forgets its image fails here instead of serving a broken preview.
"""

from pathlib import Path

from django.conf import settings
from django.template import Context, Template
from django.template.loader import render_to_string
from django.test import RequestFactory, SimpleTestCase, TestCase
from PIL import Image

from core.settings.common import build_static_dirs
from date.templatetags.social_meta import APPLE_TOUCH_ICON, SHARE_IMAGE, SHARE_IMAGE_HEIGHT, SHARE_IMAGE_WIDTH

# Deployed associations. Static dirs do not inherit parent variants, so each one
# needs its own files unless it deliberately keeps the shared DaTe card.
VARIANTS = ('date', 'kk', 'biocum', 'pulterit', 'impuls', 'sf', 'demo')
# The shared tree is the fallback and the DaTe branding, so date resolves there.
SHARED_OWNER = {'date': 'common'}
EXPECTED_SIZES = {
    SHARE_IMAGE: (SHARE_IMAGE_WIDTH, SHARE_IMAGE_HEIGHT),
    APPLE_TOUCH_ICON: (180, 180),
}


def render_tag(request=None):
    template = Template('{% load social_meta %}{% social_meta %}')
    return template.render(Context({'request': request}))


def resolve_static(name, variant):
    """Return the file the static finders would serve for ``variant``."""
    for root in build_static_dirs(variant):
        candidate = Path(root) / name
        if candidate.is_file():
            return candidate
    return None


class SocialMetaTagTests(SimpleTestCase):
    def test_renders_the_image_as_an_absolute_url(self):
        html = render_tag(RequestFactory().get('/nyheter/'))

        self.assertIn(f'<meta property="og:image" content="http://testserver/static/{SHARE_IMAGE}">', html)
        self.assertIn(f'<meta name="twitter:image" content="http://testserver/static/{SHARE_IMAGE}">', html)
        self.assertIn('<meta name="twitter:card" content="summary_large_image">', html)
        self.assertIn(f'<meta property="og:image:width" content="{SHARE_IMAGE_WIDTH}">', html)
        self.assertIn(f'<meta property="og:image:height" content="{SHARE_IMAGE_HEIGHT}">', html)
        self.assertIn('rel="apple-touch-icon"', html)
        self.assertIn(f'sizes="180x180"\n      href="http://testserver/static/{APPLE_TOUCH_ICON}"', html)

    def test_names_the_association_and_the_canonical_url(self):
        html = render_tag(RequestFactory().get('/nyheter/'))

        self.assertIn(
            f'<meta property="og:site_name" content="{settings.CONTENT_VARIABLES["ASSOCIATION_NAME"]}">',
            html,
        )
        self.assertIn('<meta property="og:url" content="http://testserver/nyheter/">', html)
        self.assertIn(
            f'content="{settings.CONTENT_VARIABLES["ASSOCIATION_NAME_FULL"]} logo"',
            html,
        )

    def test_falls_back_to_the_site_url_without_a_request(self):
        # Rendered outside a request (a management command, an email preview).
        html = render_tag()

        site_url = settings.CONTENT_VARIABLES['SITE_URL'].rstrip('/')
        self.assertIn(f'<meta property="og:image" content="{site_url}/static/{SHARE_IMAGE}">', html)
        self.assertNotIn('og:url', html)


class ShareImageAssetTests(SimpleTestCase):
    def test_every_variant_resolves_its_own_png(self):
        for variant in VARIANTS:
            for name, expected_size in EXPECTED_SIZES.items():
                with self.subTest(variant=variant, file=name):
                    path = resolve_static(name, variant)

                    self.assertIsNotNone(path, f'{variant} has no {name} in its static dirs')
                    self.assertEqual(path.parts[-4], SHARED_OWNER.get(variant, variant))
                    self.assertLess(path.stat().st_size, 500 * 1024)
                    with Image.open(path) as image:
                        self.assertEqual(image.format, 'PNG')
                        self.assertEqual(image.size, expected_size)


class BaseTemplateTests(TestCase):
    """The tag has to be wired into the shared head, not just be importable."""

    def test_base_template_renders_the_preview_image(self):
        html = render_to_string('core/base.html', {}, request=RequestFactory().get('/'))

        self.assertIn('property="og:image"', html)
        self.assertIn('name="twitter:image"', html)
        self.assertIn('rel="apple-touch-icon"', html)
