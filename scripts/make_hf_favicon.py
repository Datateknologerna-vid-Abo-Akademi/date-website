#!/usr/bin/env python3
"""Render the HF favicon from the traced hero logo.

The arc lettering is dropped and the viewBox is cropped to the round emblem,
because at 16 to 32 pixels the lettering is unreadable and only costs
contrast.  Run from the repository root::

    uv run --with cairosvg python3 scripts/make_hf_favicon.py
"""

from __future__ import annotations

import re
from pathlib import Path

import cairosvg

SOURCE = Path("templates/hf/svg/logo.svg")
OUTPUT = Path("static/hf/core/images/favicon.png")
SIZE = 180

# The emblem, without the arc text that sits outside the ring.
CROP = "110 100 1290 1290"
BACKGROUND = "#191970"
INK = "#ffffff"


def main() -> None:
    svg = SOURCE.read_text()
    svg = re.sub(r'viewBox="[^"]+"', f'viewBox="{CROP}"', svg, count=1)
    svg = svg.replace('fill="currentColor"', f'fill="{INK}"')
    svg = re.sub(r'\s*<path class="hf-letter"[^>]*/>', "", svg)

    cairosvg.svg2png(
        bytestring=svg.encode(),
        write_to=str(OUTPUT),
        output_width=SIZE,
        output_height=SIZE,
        background_color=BACKGROUND,
    )
    print(f"Wrote {OUTPUT} ({OUTPUT.stat().st_size} bytes, {SIZE}x{SIZE})")


if __name__ == "__main__":
    main()
