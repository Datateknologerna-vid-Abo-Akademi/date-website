#!/usr/bin/env python3
"""Render the footer logo from the traced hero artwork.

The footer sits on the navy page background, so the mark is baked to white:
an ``<img>`` has no inherited colour and the traced file paints itself with
``currentColor``, which would otherwise resolve to black.  An intrinsic size is
added as well, because the footer sizes the mark with ``max-height`` and an SVG
that carries only a ``viewBox`` has no default size to scale from.

Run from the repository root::

    python3 scripts/make_hf_footer_logo.py
"""

from __future__ import annotations

import re
from pathlib import Path

SOURCE = Path("templates/hf/svg/logo.svg")
OUTPUT = Path("static/hf/core/images/hf-logo-white.svg")
INK = "#ffffff"
INTRINSIC_SIZE = 600

BANNER = (
    "<!-- Generated from templates/hf/svg/logo.svg by "
    "scripts/make_hf_footer_logo.py;\n"
    "     edit the source artwork, not this file. -->"
)


def main() -> None:
    svg = SOURCE.read_text()

    svg, fills = re.subn(r'fill="currentColor"', f'fill="{INK}"', svg, count=1)
    if fills != 1:
        raise SystemExit("expected exactly one currentColor fill in the source artwork")

    svg, roots = re.subn(
        r'(<svg xmlns="http://www.w3.org/2000/svg") viewBox=',
        rf'\1 width="{INTRINSIC_SIZE}" height="{INTRINSIC_SIZE}" viewBox=',
        svg,
        count=1,
    )
    if roots != 1:
        raise SystemExit("expected a viewBox on the root svg element")

    declaration, separator, body = svg.partition("?>\n")
    if not separator:
        raise SystemExit("expected an XML declaration")
    svg = f"{declaration}?>\n{BANNER}\n{body}"

    OUTPUT.write_text(svg)
    print(f"Wrote {OUTPUT} ({OUTPUT.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
