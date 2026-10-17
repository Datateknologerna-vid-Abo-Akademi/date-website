"""The parity harness's style probe has to cover what the stylesheets can set.

`scripts/css_regression.py` snapshots a fixed list of properties per element rather
than every longhand the browser knows, because the full set is several hundred
entries per element and most of them never appear in this project. A fixed list has
one failure mode that matters: a maintainer starts using a property the probe never
records, and the harness cannot see that property change. The guard below compares the
list against what the sheets actually declare, so the list cannot drift behind them.

Real properties that the probe deliberately does not record are named in
`NOT_PROBED` with the reason. Everything else a sheet declares must be probed.
"""

from __future__ import annotations

import re
from pathlib import Path

from django.test import SimpleTestCase

from scripts.css_regression import STYLE_PROPERTIES

BASE_DIR = Path(__file__).resolve().parents[2]
STATIC_DIR = BASE_DIR / "static"
COMMENT = re.compile(r"/\*.*?\*/", re.S)
DECLARATION = re.compile(r"(?m)^\s*([a-zA-Z-]+)\s*:")

# Shorthands resolve into the longhands the probe records, so the shorthand name
# never appears in a computed style and does not need its own entry.
SHORTHANDS = frozenset(
    {
        "animation",
        "background",
        "border",
        "border-bottom",
        "border-color",
        "border-left",
        "border-right",
        "border-top",
        "border-width",
        "flex",
        "font",
        "grid",
        "grid-area",
        "grid-column",
        "grid-row",
        "grid-template",
        "inset",
        "list-style",
        "margin",
        "outline",
        "overflow",
        "padding",
        "place-content",
        "place-items",
        "place-self",
        "text-decoration",
        "transition",
        "columns",
        "border-block",
        "border-inline",
        "scroll-margin",
        "scroll-padding",
    }
)

# Recorded elsewhere, or deliberately left out.
NOT_PROBED = {
    "animation-play-state": "the override CSS forces animation: none, so it cannot vary",
    "clip": "deprecated, not used by any sheet in a way that paints",
    "grid-gap": "legacy alias of gap, which is probed",
    "grid-column-gap": "legacy alias of column-gap, which is probed",
    "grid-row-gap": "legacy alias of row-gap, which is probed",
    "td": "matched inside a selector, not a declaration",
    "th": "matched inside a selector, not a declaration",
    "tr": "matched inside a selector, not a declaration",
}


def declared_properties() -> dict[str, set[str]]:
    """Return ``{property: files}`` for every property the project's sheets declare."""
    found: dict[str, set[str]] = {}
    for path in sorted(STATIC_DIR.rglob("*.css")):
        if path.name.endswith(".min.css") or "vendor" in path.parts:
            continue
        text = COMMENT.sub("", path.read_text(encoding="utf-8"))
        for match in DECLARATION.finditer(text):
            found.setdefault(match.group(1).lower(), set()).add(path.relative_to(BASE_DIR).as_posix())
    return found


class StyleProbeCoverageTests(SimpleTestCase):
    def test_every_declared_property_is_probed(self):
        probed = set(STYLE_PROPERTIES)
        uncovered: list[str] = []
        for name, files in sorted(declared_properties().items()):
            if name in probed or name in SHORTHANDS or name in NOT_PROBED:
                continue
            if name.startswith("--") or name.startswith(("-moz-", "-ms-", "-o-", "-webkit-")):
                continue
            uncovered.append(f"{name} (declared in {', '.join(sorted(files)[:2])})")
        self.assertEqual(
            uncovered,
            [],
            "A stylesheet declares a property the parity harness never records, so a change "
            "to it cannot be detected. Add it to STYLE_PROPERTIES in scripts/css_regression.py, "
            "or name it in NOT_PROBED here with the reason it does not matter",
        )

    def test_the_probe_list_has_no_custom_properties(self):
        # A custom property's value only matters through the longhand it feeds, and
        # those are probed; recording the token itself would be noise.
        offenders = [name for name in STYLE_PROPERTIES if name.startswith("--")]
        self.assertEqual(offenders, [], "STYLE_PROPERTIES must list longhands, not custom properties")
