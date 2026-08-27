import os
import subprocess
import sys

from django.test import SimpleTestCase

EXPECTED_PREFIXES = {
    "date": ["/news/", "/archive/", "/ctf/", "/alumni/", "/publications/"],
    "kk": ["/lucia/", "/publications/", "/alumni/"],
    "biocum": ["/publications/"],
    "pulterit": ["/publications/", "/archive/"],
    "sf": ["/klotterplanket/", "/publications/"],
    "impuls": ["/alumni/", "/publications/"],
    "demo": ["/news/"],
}

CODE = """
import importlib
import os
import sys

variant = sys.argv[1]
os.environ.setdefault("PROJECT_NAME", variant)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", f"core.settings.{variant}")
import django

django.setup()

module = importlib.import_module(f"core.urls.{variant}")
paths = {str(p.pattern) for p in module.urlpatterns}
for prefix in sys.argv[2].split(","):
    if prefix not in paths:
        print(f"MISSING {prefix}")
        raise SystemExit(1)
print("OK")
"""


class VariantRouteParityTests(SimpleTestCase):
    """Each variant must expose its expected route prefixes (regression guard
    for the route-key rewrite). Runs in a fresh process so the variant's own
    INSTALLED_APPS are active."""

    def test_variant_route_parity(self):
        for variant, prefixes in EXPECTED_PREFIXES.items():
            with self.subTest(variant=variant):
                result = subprocess.run(
                    [sys.executable, "-c", CODE, variant, ",".join(prefixes)],
                    capture_output=True,
                    text=True,
                    env={**os.environ, "PROJECT_NAME": variant},
                )
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
