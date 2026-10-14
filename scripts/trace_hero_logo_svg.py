#!/usr/bin/env python3
"""Trace a hero logo raster into a staged, animated SVG.

The association hero logos are inline SVG templates that a small script
draws with a stroked trace (see ``static/<variant>/date/js/``).  For that to
work the SVG needs one ``<path>`` per visual element, ordered in the sequence
the logo should draw itself, rather than one giant path.

This script does the segmentation and the ordering:

* the raster is split into connected components
* components are classified by their distance from the centre into the disc,
  the outer ring, the ring's bead dots, the arc lettering, and the fine
  detail inside the disc
* each component is traced on its own with potrace, so a letter keeps its
  counters inside the same path element
* paths are emitted in draw order: ring, beads, arc text in reading order,
  then the disc and its interior detail

Run it from the repository root::

    uv run --with pillow --with numpy --with scipy python3 \
        scripts/trace_hero_logo_svg.py \
        --source static/hf/core/images/hf-logo.png \
        --output templates/hf/svg/logo.svg \
        --label "Humanistiska föreningen vid Åbo Akademi"

potrace must be on PATH.
"""

from __future__ import annotations

import argparse
import math
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage

ALPHA_THRESHOLD = 128
MIN_COMPONENT_PIXELS = 40
DRAW_ORDER = ("ring", "ring-dot", "letter", "disc", "detail")

# The source art is flat two-tone line work, so a low speckle filter and the
# default corner detection give clean curves.
POTRACE_ARGS = ("--svg", "--turdsize", "2", "--alphamax", "1.0", "--opttolerance", "0.2")

NUMBER = re.compile(r"-?\d*\.?\d+(?:e-?\d+)?")
TOKEN = re.compile(r"[A-Za-z]|-?\d*\.?\d+(?:e-?\d+)?")
# The command letters potrace emits, with the number of coordinate pairs each
# one takes. z takes none. Anything else is treated as a failure rather than
# guessed at.
COMMAND_ARITY = {"M": 1, "L": 1, "C": 3}
MOVE = re.compile(r"\s*(-?\d*\.?\d+(?:e-?\d+)?)[\s,]+(-?\d*\.?\d+(?:e-?\d+)?)", re.S)
POTRACE_TRANSFORM = re.compile(r'transform="translate\(([-\d.]+),([-\d.]+)\)\s*scale\(([-\d.]+),([-\d.]+)\)"')
PATH_DATA = re.compile(r"<path[^>]*\sd=\"([^\"]+)\"", re.S)
SUB_PATH = re.compile(r"[Mm][^Mm]*")


@dataclass
class Component:
    """One connected dark region of the source art."""

    index: int
    pixels: int
    mask: np.ndarray
    centroid: tuple[float, float]
    bbox_span: float
    angle: float = 0.0
    mean_radius: float = 0.0
    min_radius: float = 0.0
    max_radius: float = 0.0
    group: str = "detail"
    order: float = 0.0
    path_data: str = ""


@dataclass
class TracedLogo:
    width: int
    height: int
    transform: str
    groups: dict[str, list[Component]] = field(default_factory=dict)


def load_mask(source: Path) -> np.ndarray:
    return np.array(Image.open(source).convert("RGBA"))[..., 3] > ALPHA_THRESHOLD


def label_components(mask: np.ndarray) -> list[Component]:
    labels, count = ndimage.label(mask, structure=np.ones((3, 3)))
    sizes = ndimage.sum(mask, labels, range(1, count + 1))
    components: list[Component] = []
    for offset in range(count):
        index = offset + 1
        pixels = int(sizes[offset])
        if pixels < MIN_COMPONENT_PIXELS:
            continue
        component_mask = labels == index
        comp_ys, comp_xs = np.where(component_mask)
        components.append(
            Component(
                index=index,
                pixels=pixels,
                mask=component_mask,
                centroid=(float(comp_xs.mean()), float(comp_ys.mean())),
                bbox_span=math.hypot(comp_xs.max() - comp_xs.min(), comp_ys.max() - comp_ys.min()),
            )
        )
    if not components:
        raise SystemExit("No components found above the size threshold")
    return components


def measure(components: list[Component], centre: tuple[float, float]) -> None:
    """Fill in each component's polar coordinates about the art's real centre.

    The canvas centre is not good enough: the disc is drawn slightly off
    centre and its inked figure pushes its centroid sideways, which would blur
    the radius bands that separate the ring beads from the disc.
    """
    centre_x, centre_y = centre
    for component in components:
        ys, xs = np.where(component.mask)
        radii = np.hypot(xs - centre_x, ys - centre_y)
        centroid_x, centroid_y = component.centroid
        component.angle = math.degrees(math.atan2(centroid_y - centre_y, centroid_x - centre_x)) % 360.0
        component.mean_radius = float(radii.mean())
        component.min_radius = float(radii.min())
        component.max_radius = float(radii.max())


def classify(components: list[Component]) -> dict[str, list[Component]]:
    """Sort components into draw groups using their distance from the centre.

    The art is concentric, so radius bands separate the layers cleanly: the
    solid disc is the largest component and the ring is the thin circle whose
    bounding box spans the most.  Anything outside the ring is arc lettering,
    anything in the gap between the disc edge and the ring is one of the
    ring's bead dots, and the rest is detail inside the disc.
    """
    disc = max(components, key=lambda c: c.pixels)
    rest = [c for c in components if c is not disc]
    ring = max(rest, key=lambda c: c.bbox_span)
    rest = [c for c in rest if c is not ring]
    measure(components, ring.centroid)

    groups: dict[str, list[Component]] = {
        "ring": [ring],
        "ring-dot": [],
        "letter": [],
        "disc": [disc],
        "detail": [],
    }
    for component in rest:
        if component.mean_radius > ring.max_radius:
            component.group = "letter"
        elif component.mean_radius > disc.max_radius:
            component.group = "ring-dot"
        else:
            component.group = "detail"
        groups[component.group].append(component)

    order_groups(groups)
    return groups


def order_groups(groups: dict[str, list[Component]]) -> None:
    """Set the draw order inside each group.

    Beads sweep clockwise from the left.  Arc lettering runs in reading
    order, which is increasing angle along the top arc and decreasing angle
    along the bottom one.  Interior detail follows the arc it sits on.
    """
    for component in groups["ring-dot"]:
        component.order = (component.angle - 180.0) % 360.0
    groups["ring-dot"].sort(key=lambda c: c.order)

    top_arc = sorted((c for c in groups["letter"] if c.angle >= 180.0), key=lambda c: c.angle)
    bottom_arc = sorted((c for c in groups["letter"] if c.angle < 180.0), key=lambda c: -c.angle)
    groups["letter"] = top_arc + bottom_arc
    for position, component in enumerate(groups["letter"]):
        component.order = float(position)

    groups["detail"].sort(key=lambda c: c.angle)
    for position, component in enumerate(groups["detail"]):
        component.order = float(position)


def write_pbm(mask: np.ndarray, destination: Path) -> None:
    height, width = mask.shape
    with destination.open("wb") as handle:
        handle.write(f"P4\n{width} {height}\n".encode())
        handle.write(np.packbits(mask, axis=1).tobytes())


def trace_mask(mask: np.ndarray, workdir: Path) -> tuple[str, str]:
    """Trace one bitmap and return potrace's group transform and path data."""
    pbm = workdir / "layer.pbm"
    svg = workdir / "layer.svg"
    write_pbm(mask, pbm)
    subprocess.run(
        ["potrace", *POTRACE_ARGS, "--output", str(svg), str(pbm)],
        check=True,
        capture_output=True,
    )
    text = svg.read_text()
    transform_match = POTRACE_TRANSFORM.search(text)
    path_match = PATH_DATA.search(text)
    if not transform_match or not path_match:
        raise SystemExit("potrace produced no path for a layer")
    return (
        "translate({},{}) scale({},{})".format(*transform_match.groups()),
        path_match.group(1),
    )


def subpath_points(subpath: str) -> list[tuple[float, float]]:
    """Every on-path point of a subpath, resolved to absolute coordinates.

    potrace writes the first subpath with an absolute ``M`` and then mixes
    absolute and relative commands, and a single command letter can carry many
    coordinate groups (one ``c`` followed by every curve of the contour).  The
    numbers therefore cannot be read pairwise: a relative control point is an
    offset from the current point, not a position.  Walking the commands in
    order is what makes the resulting bounds, and so the contour ordering in
    ``order_disc_subpaths``, mean what they claim.
    """
    tokens = TOKEN.findall(subpath)
    points: list[tuple[float, float]] = []
    current_x = current_y = 0.0
    start_x = start_y = 0.0
    index = 0

    while index < len(tokens):
        command = tokens[index]
        index += 1
        if command in "Zz":
            current_x, current_y = start_x, start_y
            continue

        arity = COMMAND_ARITY.get(command.upper())
        if arity is None:
            raise SystemExit(f"Unsupported path command {command!r} in potrace output")
        relative = command.islower()

        while index < len(tokens) and not tokens[index].isalpha():
            if index + arity * 2 > len(tokens):
                raise SystemExit(f"Truncated subpath from potrace: {subpath[:40]!r}")
            # Every coordinate in one command is relative to the point the
            # command starts from, so the control points must not be chained
            # through each other. Only the last pair moves the current point.
            base_x, base_y = current_x, current_y
            group: list[tuple[float, float]] = []
            for _ in range(arity):
                x = float(tokens[index])
                y = float(tokens[index + 1])
                index += 2
                if relative:
                    x, y = base_x + x, base_y + y
                group.append((x, y))
            points.extend(group)
            current_x, current_y = group[-1]

        if command.upper() == "M":
            start_x, start_y = current_x, current_y

    if not points:
        raise SystemExit(f"Subpath with no coordinates from potrace: {subpath[:40]!r}")
    return points


def subpath_bounds(subpath: str) -> tuple[float, float, float, float]:
    points = subpath_points(subpath)
    xs = [x for x, _ in points]
    ys = [y for _, y in points]
    return min(xs), min(ys), max(xs), max(ys)


def format_number(value: float) -> str:
    """Shortest representation that reads back as the same float."""
    return str(int(value)) if float(value).is_integer() else repr(value)


def absolute_subpaths(path_data: str) -> list[str]:
    """Rewrite every subpath to start with its own absolute moveto.

    potrace writes the first subpath with an absolute ``M`` and each later one
    with a relative ``m`` measured from the end of the previous subpath.  Every
    subpath is closed, so that end point is the previous subpath's own start,
    and the chain can be resolved by walking them in order.  Splitting or
    reordering the subpaths is only safe once each carries an absolute move.
    """
    resolved: list[str] = []
    current_x = current_y = 0.0
    for subpath in SUB_PATH.findall(path_data):
        command, body = subpath[0], subpath[1:]
        move = MOVE.match(body)
        if move is None:
            raise SystemExit(f"Unparseable subpath from potrace: {subpath[:40]!r}")
        delta_x, delta_y = float(move.group(1)), float(move.group(2))
        if command == "M":
            current_x, current_y = delta_x, delta_y
        else:
            current_x += delta_x
            current_y += delta_y
        rest = body[move.end() :]
        resolved.append(f"M{format_number(current_x)} {format_number(current_y)}{rest}")
    return resolved


def order_disc_subpaths(path_data: str) -> str:
    """Order the disc's contours for a stroke trace, smallest detail first.

    The interior contours are drawn before the disc outline and sorted top to
    bottom, so a hero animation draws the figure and then closes the circle
    around it.  Drawn the other way round, the outline leads and the viewer
    spends the longest phase of the animation looking at a large circle with an
    obvious gap in it, which reads as an unfinished drawing rather than as an
    intentional one.

    potrace's output is y-up, so the topmost contour of the art has the largest
    y coordinate and the contours sort by descending upper bound.
    """
    subpaths = absolute_subpaths(path_data)
    if len(subpaths) < 2:
        return "".join(subpaths)

    def area(subpath: str) -> float:
        x0, y0, x1, y1 = subpath_bounds(subpath)
        return (x1 - x0) * (y1 - y0)

    outline = max(subpaths, key=area)
    detail = [s for s in subpaths if s != outline]
    detail.sort(key=lambda s: subpath_bounds(s)[3], reverse=True)
    return "".join([*detail, outline])


def build_svg(logo: TracedLogo, label: str) -> str:
    lines = [
        '<?xml version="1.0" encoding="utf-8"?>',
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {logo.width} {logo.height}"',
        f'     role="img" aria-label="{label}">',
        f"  <title>{label}</title>",
        f'  <g class="hf-logo-art" transform="{logo.transform}"',
        '     fill="currentColor" fill-rule="evenodd" stroke="none">',
    ]
    for group in DRAW_ORDER:
        for component in logo.groups.get(group, []):
            lines.append(f'    <path class="hf-{group}" d="{component.path_data}"/>')
    lines.extend(["  </g>", "</svg>", ""])
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--label", required=True)
    args = parser.parse_args()

    if not shutil.which("potrace"):
        raise SystemExit("potrace is required and was not found on PATH")

    mask = load_mask(args.source)
    height, width = mask.shape
    groups = classify(label_components(mask))

    transforms: set[str] = set()
    with tempfile.TemporaryDirectory() as tmp:
        workdir = Path(tmp)
        for group, members in groups.items():
            for component in members:
                transform, path_data = trace_mask(component.mask, workdir)
                transforms.add(transform)
                if group == "disc":
                    path_data = order_disc_subpaths(path_data)
                else:
                    # Absolute moves everywhere, so a consumer may split a
                    # path into subpaths without changing the geometry.
                    path_data = "".join(absolute_subpaths(path_data))
                component.path_data = path_data

    if len(transforms) != 1:
        raise SystemExit(f"Layers traced at differing scales: {sorted(transforms)}")

    logo = TracedLogo(width=width, height=height, transform=transforms.pop(), groups=groups)
    print("Trace groups: " + ", ".join(f"{g}={len(groups[g])}" for g in DRAW_ORDER))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(build_svg(logo, args.label))
    print(f"Wrote {args.output} ({args.output.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
