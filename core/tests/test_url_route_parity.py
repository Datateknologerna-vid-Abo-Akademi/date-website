import os
import subprocess
import sys

from django.test import SimpleTestCase

from core.urls.common import build_urlpatterns

COMMON_PREFIXES = ["healthz/", "readyz/"]
# Every current variant requests 'events', which has an API_ROUTES entry, so
# the shared api/ root is assembled right before the trailing group in all of
# them. See core.urls.common.build_urlpatterns.
API_PREFIXES = ["api/"]
TRAILING_PREFIXES = ["set_lang/", "jsi18n/", "_uploads/sign/"]

EXPECTED_PREFIXES = {
    "date": [
        *COMMON_PREFIXES,
        "",
        "news/",
        "members/",
        "members/two-factor/",
        "archive/",
        "events/",
        "pages/",
        "forms/",
        "ads/",
        "social/",
        "polls/",
        "ctf/",
        "admin/",
        "ckeditor5/",
        "publications/",
        "alumni/",
        *API_PREFIXES,
        *TRAILING_PREFIXES,
    ],
    "kk": [
        *COMMON_PREFIXES,
        "",
        "news/",
        "members/",
        "members/two-factor/",
        "archive/",
        "events/",
        "pages/",
        "forms/",
        "ads/",
        "social/",
        "polls/",
        "lucia/",
        "admin/",
        "ckeditor5/",
        "publications/",
        "alumni/",
        *API_PREFIXES,
        *TRAILING_PREFIXES,
    ],
    "biocum": [
        *COMMON_PREFIXES,
        "",
        "news/",
        "members/",
        "members/two-factor/",
        "archive/",
        "events/",
        "pages/",
        "forms/",
        "ads/",
        "social/",
        "polls/",
        "admin/",
        "ckeditor5/",
        "publications/",
        *API_PREFIXES,
        *TRAILING_PREFIXES,
    ],
    "pulterit": [
        *COMMON_PREFIXES,
        "",
        "news/",
        "members/",
        "members/two-factor/",
        "archive/",
        "events/",
        "pages/",
        "forms/",
        "ads/",
        "social/",
        "polls/",
        "admin/",
        "ckeditor5/",
        "publications/",
        *API_PREFIXES,
        *TRAILING_PREFIXES,
    ],
    "sf": [
        *COMMON_PREFIXES,
        "",
        "news/",
        "members/",
        "members/two-factor/",
        "archive/",
        "events/",
        "pages/",
        "forms/",
        "ads/",
        "social/",
        "polls/",
        "admin/",
        "ckeditor5/",
        "publications/",
        "klotterplanket/",
        *API_PREFIXES,
        *TRAILING_PREFIXES,
    ],
    "impuls": [
        *COMMON_PREFIXES,
        "",
        "news/",
        "members/",
        "members/two-factor/",
        "archive/",
        "events/",
        "pages/",
        "forms/",
        "ads/",
        "social/",
        "polls/",
        "admin/",
        "ckeditor5/",
        "publications/",
        "alumni/",
        *API_PREFIXES,
        *TRAILING_PREFIXES,
    ],
    "demo": [
        *COMMON_PREFIXES,
        "",
        "news/",
        "members/",
        "members/two-factor/",
        "archive/",
        "events/",
        "pages/",
        "forms/",
        "ads/",
        "social/",
        "polls/",
        "admin/",
        "ckeditor5/",
        *API_PREFIXES,
        *TRAILING_PREFIXES,
    ],
}

EXPECTED_URL_NAMES = {
    "date": [
        "news:index",
        "archive:years",
        "ctf:index",
        "publications:pdf_list",
        "alumni:alumni_signup",
        "api:events:upcoming",
    ],
    "kk": ["news:index", "lucia:index", "publications:pdf_list", "alumni:alumni_signup", "api:events:upcoming"],
    "biocum": ["news:index", "archive:years", "publications:pdf_list", "api:events:upcoming"],
    "pulterit": ["news:index", "archive:exams", "publications:pdf_list", "api:events:upcoming"],
    "sf": ["news:index", "archive:years", "publications:pdf_list", "klotterplanket:index", "api:events:upcoming"],
    "impuls": [
        "news:index",
        "archive:years",
        "publications:pdf_list",
        "alumni:alumni_signup",
        "api:events:upcoming",
    ],
    "demo": ["news:index", "archive:years", "api:events:upcoming"],
}

FORBIDDEN_URL_NAMES = {
    "pulterit": ["archive:years"],
}

CODE = """
import importlib
import os
import sys

from django.urls import NoReverseMatch, reverse

variant = sys.argv[1]
os.environ["PROJECT_NAME"] = variant
os.environ["DJANGO_SETTINGS_MODULE"] = f"core.settings.{variant}"
os.environ["DATE_DEBUG"] = "0"
import django

django.setup()

module = importlib.import_module(f"core.urls.{variant}")
expected_paths = sys.argv[2].split(",")
actual_paths = [str(p.pattern) for p in module.urlpatterns]
if actual_paths != expected_paths:
    print(f"EXPECTED {expected_paths}")
    print(f"ACTUAL {actual_paths}")
    raise SystemExit(1)

for name in sys.argv[3].split(","):
    try:
        reverse(name, urlconf=module)
    except NoReverseMatch:
        print(f"MISSING URL {name}")
        raise SystemExit(1)

for name in filter(None, sys.argv[4].split(",")):
    try:
        reverse(name, urlconf=module)
    except NoReverseMatch:
        continue
    print(f"UNEXPECTED URL {name}")
    raise SystemExit(1)
print("OK")
"""


class VariantRouteParityTests(SimpleTestCase):
    """Each variant must expose its complete route inventory and named URLs.

    Runs in a fresh process so the variant's own INSTALLED_APPS are active.
    """

    def test_variant_route_parity(self):
        for variant, prefixes in EXPECTED_PREFIXES.items():
            with self.subTest(variant=variant):
                result = subprocess.run(
                    [
                        sys.executable,
                        "-c",
                        CODE,
                        variant,
                        ",".join(prefixes),
                        ",".join(EXPECTED_URL_NAMES[variant]),
                        ",".join(FORBIDDEN_URL_NAMES.get(variant, [])),
                    ],
                    capture_output=True,
                    text=True,
                    env={**os.environ, "PROJECT_NAME": variant},
                )
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


class ApiRootCompositionTests(SimpleTestCase):
    """The shared /api/ root only appears for routes with an API_ROUTES
    entry that were also requested, so leaving a capability's key out of
    build_urlpatterns(...) removes its API surface too, with no separate
    toggle to remember and no import of the disabled app's api_urls module.
    """

    def test_api_root_present_when_events_requested(self):
        patterns = build_urlpatterns('index', 'events')
        self.assertIn("api/", [str(p.pattern) for p in patterns])

    def test_api_root_absent_when_events_not_requested(self):
        patterns = build_urlpatterns('index')
        self.assertNotIn("api/", [str(p.pattern) for p in patterns])
