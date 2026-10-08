"""Guard against unscoped ``nav`` selectors in project stylesheets.

Stylesheets are loaded on every page, so an element selector such as a bare
``nav`` also matches the pagination navs (django-tables2's table pagination, the
gallery fallback, publications). Header and "hide the chrome" rules must be
scoped, e.g. ``nav.navbar``.

The scanner walks the stylesheets brace by brace, so nested rules and
``@media`` blocks are scanned like flat ones.
"""

import re
from collections.abc import Iterator
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

COMMENT = re.compile(r"/\*.*?\*/", re.S)
NAV_TOKEN = re.compile(r"(?<![\w.#-])nav(?![\w-])", re.IGNORECASE)
SCOPE_CHARS = (".", "#", "[")
PAGINATION_SHEET = Path("static/common/core/css/pagination.css")
# Styling has to sit inside django-tables2's wrapper, not beside it. The wrapper
# itself is allowed, because the sheet defines its colour tokens on it.
WRAPPER_SCOPE = re.compile(r"^\.table-container(?![\w-])(?:\s*>\s*|\s+)(?![+~])\S")
WRAPPER_ONLY = re.compile(r"^\.table-container(?![\w-])$")


def iter_selectors(css: str) -> Iterator[str]:
    """Yield every selector in a stylesheet, including nested and at-rule blocks."""
    pending: list[str] = []
    for char in COMMENT.sub("", css):
        if char == "{":
            prelude = "".join(pending).strip()
            pending = []
            if not prelude or prelude.startswith("@"):
                continue
            for selector in prelude.split(","):
                selector = " ".join(selector.split())
                if selector:
                    yield selector
        elif char == "}":
            pending = []
        else:
            pending.append(char)


def unscoped_nav_selectors(css: str):
    """Return the selectors that match a ``nav`` element without a class or id."""
    offenders = []
    for selector in iter_selectors(css):
        for match in NAV_TOKEN.finditer(selector):
            if selector[match.end() : match.end() + 1] not in SCOPE_CHARS:
                offenders.append(selector)
    return offenders


class StylesheetNavScopeTests(SimpleTestCase):
    def test_project_stylesheets_scope_nav_selectors(self):
        base_dir = Path(settings.BASE_DIR)
        offenders = []
        for path in sorted((base_dir / "static").rglob("*.css")):
            if path.name.endswith(".min.css") or "vendor" in path.parts:
                continue
            for selector in unscoped_nav_selectors(path.read_text(encoding="utf-8")):
                offenders.append(f"{path.relative_to(base_dir)}: {selector}")

        self.assertEqual(offenders, [], "Unscoped nav selectors leak onto pagination navs")

    def test_scanner_reports_unscoped_nav_rules(self):
        self.assertEqual(unscoped_nav_selectors("nav { color: red; }"), ["nav"])
        self.assertEqual(unscoped_nav_selectors("nav:hover { color: red; }"), ["nav:hover"])
        self.assertEqual(unscoped_nav_selectors("NAV { color: red; }"), ["NAV"])
        self.assertEqual(unscoped_nav_selectors("nav, footer { display: none; }"), ["nav"])
        self.assertEqual(unscoped_nav_selectors("@media (min-width: 1px) { nav { color: red; } }"), ["nav"])
        self.assertEqual(unscoped_nav_selectors("nav { & a { color: red; } }"), ["nav"])
        # An ancestor alone is not enough: pagination navs are nested inside the
        # same page containers, so the nav itself must be qualified.
        self.assertEqual(unscoped_nav_selectors("#header nav { color: red; }"), ["#header nav"])
        self.assertEqual(unscoped_nav_selectors(".content nav { color: red; }"), [".content nav"])

    def test_scanner_accepts_scoped_nav_rules(self):
        self.assertEqual(unscoped_nav_selectors(".navbar { color: red; }"), [])
        self.assertEqual(unscoped_nav_selectors("nav.navbar { color: red; }"), [])
        self.assertEqual(unscoped_nav_selectors("nav[aria-label] { color: red; }"), [])
        self.assertEqual(unscoped_nav_selectors(".navigation nav.navbar { color: red; }"), [])


class PaginationStylesheetTests(SimpleTestCase):
    def test_shared_pagination_rules_are_scoped_beneath_the_tables2_wrapper(self):
        css = (Path(settings.BASE_DIR) / PAGINATION_SHEET).read_text(encoding="utf-8")
        selectors = list(iter_selectors(css))

        self.assertTrue(selectors)
        offenders = [
            selector for selector in selectors if not (WRAPPER_ONLY.match(selector) or WRAPPER_SCOPE.match(selector))
        ]
        self.assertEqual(offenders, [], "Pagination rules that escape the django-tables2 wrapper")

    def test_wrapper_scope_accepts_descendants_and_rejects_siblings(self):
        self.assertTrue(WRAPPER_ONLY.match(".table-container"))
        self.assertTrue(WRAPPER_SCOPE.match(".table-container .pagination"))
        self.assertTrue(WRAPPER_SCOPE.match(".table-container > .pagination a"))
        self.assertTrue(WRAPPER_SCOPE.match(".table-container .pagination li:nth-child(2n+1)"))
        self.assertIsNone(WRAPPER_SCOPE.match(".table-container-other .pagination"))
        self.assertIsNone(WRAPPER_SCOPE.match(".table-container + .pagination"))
        self.assertIsNone(WRAPPER_SCOPE.match(".table-container ~ .pagination"))
        self.assertIsNone(WRAPPER_SCOPE.match(".other .table-container .pagination"))
