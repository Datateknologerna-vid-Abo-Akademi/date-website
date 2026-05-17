#!/usr/bin/env python3

from pathlib import Path
import re


SOURCE = Path("templates/sf/date/svg/logo.svg")


def main() -> None:
    svg = SOURCE.read_text()

    view_box_match = re.search(r'viewBox="([^"]+)"', svg)
    path_match = re.search(r"<path[^>]*d=\"([^\"]+)\"", svg, re.S)
    if not view_box_match or not path_match:
        raise SystemExit("Could not find viewBox/path in SF logo SVG")

    subpaths = [segment.strip() for segment in re.split(r"(?=[Mm])", path_match.group(1)) if segment.strip()]
    lines = [
        '<?xml version="1.0" encoding="utf-8"?>',
        '<svg version="1.1" xmlns="http://www.w3.org/2000/svg" '
        f'viewBox="{view_box_match.group(1)}" xml:space="preserve">',
        "<g fill=\"none\">",
    ]
    lines.extend(f'    <path d="{subpath}"/>' for subpath in subpaths)
    lines.extend(["</g>", "</svg>"])

    SOURCE.write_text("\n".join(lines) + "\n")
    print(f"Wrote {SOURCE} with {len(subpaths)} path elements")


if __name__ == "__main__":
    main()
