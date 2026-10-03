"""Tests for the CKEditor 5 integration.

The editor is configured once in `core.settings.dependencies.ckeditor`, and the
stylesheet that makes its output render correctly on the public site lives in
`static/common/core/css/ck-content.css`. Both are easy to break without noticing:
CKEditor accepts unknown toolbar items and unread named configs without
complaining, and a stylesheet rule that goes missing only shows up as a
misaligned image on a live page.
"""

import re
from pathlib import Path

from django.conf import settings
from django.contrib.staticfiles import finders
from django.test import SimpleTestCase

DEFAULT_CONFIG_NAME = "default"

COMMENT_RE = re.compile(r"/\*.*?\*/", re.DOTALL)
RULE_RE = re.compile(r"([^{}]+)\{([^{}]*)\}", re.DOTALL)
AT_RULE_RE = re.compile(r"@[a-zA-Z-]+\s*[^{;]*\{")

# Shorthands and longhands that would replace the site typography wholesale.
TYPOGRAPHY_PROPERTIES = {"all", "color", "font", "font-family", "font-size", "line-height"}


def strip_at_blocks(css: str) -> str:
    """Drop at-rule blocks such as `@media`.

    The parser below only models flat rule lists, so nested rules are removed
    rather than attributed to the wrong selector. `at_block` reads them back.
    Comments must already be stripped, or a commented out block would still be
    treated as live.
    """
    result = []
    index = 0
    while index < len(css):
        if css[index] != "@":
            result.append(css[index])
            index += 1
            continue
        brace = css.find("{", index)
        semicolon = css.find(";", index)
        if brace == -1 or (semicolon != -1 and semicolon < brace):
            index = len(css) if semicolon == -1 else semicolon + 1
            continue
        depth = 1
        index = brace + 1
        while index < len(css) and depth:
            depth += (css[index] == "{") - (css[index] == "}")
            index += 1
    return "".join(result)


def parse_declarations(css: str) -> dict[str, dict[str, str]]:
    """Map every selector in a flat rule list to its effective declarations.

    Comments are stripped first, then at-rule blocks, and comma separated
    selector lists are split, so `.a, .b { float: left }` reports `float: left`
    for both `.a` and `.b`. Later declarations win, except that an `!important`
    declaration beats a later one without it, which is the part of the cascade
    that decides whether the association `!important` caps are overridden.
    """
    declarations: dict[str, dict[str, str]] = {}
    for selectors, body in RULE_RE.findall(strip_at_blocks(COMMENT_RE.sub("", css))):
        for selector in selectors.split(","):
            target = declarations.setdefault(selector.strip(), {})
            for declaration in body.split(";"):
                property_name, separator, value = declaration.partition(":")
                if not separator or not value.strip():
                    continue
                property_name = property_name.strip()
                current = target.get(property_name)
                if current and "!important" in current and "!important" not in value:
                    continue
                target[property_name] = value.strip()
    return declarations


def at_block(css: str, condition: str) -> str:
    """Return the body of the at-rule block whose prelude contains `condition`."""
    css = COMMENT_RE.sub("", css)
    for match in AT_RULE_RE.finditer(css):
        prelude_end = match.end() - 1
        if condition not in css[match.start() : prelude_end]:
            continue
        depth = 1
        index = match.end()
        while index < len(css) and depth:
            depth += (css[index] == "{") - (css[index] == "}")
            index += 1
        return css[match.end() : index - 1]
    return ""


# Every image class CKEditor can write into stored content, with the declarations
# that make it render the way the editor showed it. Losing one of these silently
# restores the bug where the alignment or the size picked in the editor was
# ignored on the public page.
IMAGE_RULES = {
    ".ck-content .image-style-align-left": {"float": "left"},
    ".ck-content .image-style-align-right": {"float": "right"},
    ".ck-content .image-style-align-center": {"margin-left": "auto", "margin-right": "auto"},
    ".ck-content .image.image-style-side": {"float": "right", "max-width": "50%"},
    ".ck-content .image.image-style-block-align-left": {"margin-left": "0", "margin-right": "auto"},
    ".ck-content .image.image-style-block-align-right": {"margin-left": "auto", "margin-right": "0"},
    ".ck-content .image-inline": {"display": "inline-flex"},
    # The association stylesheets force `width: auto !important` on content
    # images, so a resized image only keeps the stored width if these override
    # it. Dropping either one brings back the squashed or oversized resize.
    ".ck-content .image.image_resized img": {"width": "100% !important", "max-height": "none !important"},
}


class CkeditorConfigTests(SimpleTestCase):
    def test_list_properties_use_booleans_on_the_default_config(self):
        # ListProperties reads a string as the name of a single list type, so
        # 'true' would register a bogus type called "true" and neither the
        # bullet nor the number style dropdown would appear. These settings once
        # sat in a top-level `list` entry of CKEDITOR_5_CONFIGS as well, which is
        # read as a separate config name that no field asks for, so they were
        # silently dead.
        properties = settings.CKEDITOR_5_CONFIGS[DEFAULT_CONFIG_NAME]["list"]["properties"]

        self.assertEqual(properties, {"styles": True, "startIndex": True, "reversed": True})

    def test_toolbar_exposes_the_options_that_need_explicit_config(self):
        toolbar = settings.CKEDITOR_5_CONFIGS[DEFAULT_CONFIG_NAME]["toolbar"]

        for item in ("alignment", "findAndReplace", "specialCharacters", "horizontalLine", "showBlocks"):
            with self.subTest(item=item):
                self.assertIn(item, toolbar)

    def test_image_toolbar_exposes_resize_and_link(self):
        image_toolbar = settings.CKEDITOR_5_CONFIGS[DEFAULT_CONFIG_NAME]["image"]["toolbar"]

        for item in ("resizeImage", "linkImage"):
            with self.subTest(item=item):
                self.assertIn(item, image_toolbar)

    def test_upload_file_types_include_jpg(self):
        # The widget's own fallback list omits jpg, which filters .jpg files out
        # of the upload picker even though the server side accepts them.
        self.assertIn("jpg", settings.CKEDITOR_5_UPLOAD_FILE_TYPES)


class StylesheetParserTests(SimpleTestCase):
    """The stylesheet checks below are only worth anything if the parser is honest."""

    def test_a_later_plain_declaration_overrides_an_earlier_one(self):
        declarations = parse_declarations(".a { float: left; float: none; }")

        self.assertEqual(declarations[".a"]["float"], "none")

    def test_important_beats_a_later_plain_declaration(self):
        declarations = parse_declarations(".a { width: 100% !important; } .a { width: auto; }")

        self.assertEqual(declarations[".a"]["width"], "100% !important")

    def test_comma_separated_selectors_share_their_declarations(self):
        declarations = parse_declarations(".a, .b { float: left; }")

        self.assertEqual(declarations[".a"]["float"], "left")
        self.assertEqual(declarations[".b"]["float"], "left")

    def test_nested_rules_stay_out_of_the_flat_parse(self):
        declarations = parse_declarations("@media print { .a { float: left; } }")

        self.assertNotIn(".a", declarations)

    def test_commented_out_rules_are_ignored(self):
        commented = (
            "/* @media (max-width: 767.98px) { .a { display: block; } } */\n.a { float: left; } /* float: none; */\n"
        )
        declarations = parse_declarations(commented)

        self.assertEqual(declarations[".a"]["float"], "left")
        self.assertEqual(at_block(commented, "max-width: 767.98px"), "")


class CkeditorContentStylesheetTests(SimpleTestCase):
    def setUp(self):
        path = finders.find("core/css/ck-content.css")
        self.assertIsNotNone(path, "core/css/ck-content.css is not collected by the static finders")
        self.stylesheet = Path(path).read_text(encoding="utf-8")
        self.declarations = parse_declarations(self.stylesheet)

    def test_each_image_class_keeps_the_declarations_that_place_it(self):
        for selector, expected in IMAGE_RULES.items():
            with self.subTest(selector=selector):
                actual = self.declarations.get(selector, {})
                self.assertTrue(actual, f"{selector} has no top level rule in ck-content.css")
                for property_name, value in expected.items():
                    self.assertEqual(actual.get(property_name), value, f"{selector} needs {property_name}: {value}")

    def test_base_rule_does_not_reset_the_site_typography(self):
        # The bundled django-ckeditor-5 stylesheet styles `.ck-content` with its
        # own font, size, line height and colour. Loading it on the public site
        # would replace the site typography on every content page, so the
        # project keeps its own subset that leaves those alone.
        resets = sorted(set(self.declarations.get(".ck-content", {})) & TYPOGRAPHY_PROPERTIES)

        self.assertEqual(resets, [], f"ck-content.css resets the site typography with {resets}")

    def test_narrow_screens_let_a_wide_table_scroll(self):
        # A table formatting box cannot scroll, so the figure has to become a
        # plain container below the md breakpoint, otherwise a table wider than
        # the screen widens the whole page on a phone.
        mobile = parse_declarations(at_block(self.stylesheet, "max-width: 767.98px"))

        self.assertEqual(mobile.get(".ck-content figure.table", {}).get("display"), "block")
        self.assertEqual(mobile.get(".ck-content figure.table", {}).get("overflow-x"), "auto")
