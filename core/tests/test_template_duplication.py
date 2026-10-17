"""Guard against per-association templates drifting back into copies.

Static files shadow, templates override. The difference matters: a variant
template at `templates/<association>/<path>` replaces whatever would resolve there
and can only reintroduce content through `{% extends %}` and `{% block %}`, while a
variant that pastes a whole page back in has nothing keeping it in step with the
shared one. That is how the homepage events and news components ended up as five
and six copies, and how three arsfest pages became standalone rewrites of a shared
one.

This module measures how alike the copies of one logical path are and freezes the
pairs that are still alike, each with a reason. A new near-copy, a new copy at a
frozen path, or a frozen pair that gets more alike fails until the baseline is
regenerated with a reason. Copies below `MIN_LINES` are ignored on purpose: a small
`{% extends %}` plus one block override is the shape this repo wants, and it is
supposed to look similar to the association next door.

A file that only fills blocks is not compared against another override: after its
`{% block %}` bodies, comments and `{% extends %}`/`{% load %}` lines are removed
there is no markup left, so there is no page body to have been copied. That is the
shape this repository wants (`{% extends %}` plus the blocks that differ), and two
such files are supposed to look alike.

Regenerate the baseline after a deliberate change, and write the reason for every
frozen path:

    uv run python -m core.tests.test_template_duplication --write-baseline
"""

from __future__ import annotations

import difflib
import json
import re
import sys
from pathlib import Path
from typing import Any

from django.test import SimpleTestCase

BASE_DIR = Path(__file__).resolve().parents[2]
TEMPLATES_DIR = BASE_DIR / "templates"
BASELINE_PATH = Path(__file__).with_name("template_near_copy_baseline.json")

# `demo` is a stock photography demo variant and is deliberately out of scope.
ASSOCIATIONS = ("date", "kk", "biocum", "pulterit", "sf", "impuls")
SHARED = "common"

# Two copies at 0.70 or above, with both sides at least this long, are treated as
# one component that was pasted instead of shared.
THRESHOLD = 0.70
MIN_LINES = 15

# A frozen pair may not get closer than this, or the copies are drifting together.
DRIFT_MARGIN = 0.02

# Every frozen path needs a reason. This is the only place a new copy is allowed to
# be recorded, so it is also the place a maintainer explains why.
REASONS: dict[str, str] = {
    "events/arsfest.html": (
        "The Pulterit arsfest page is still a copy of DaTe's, and biocum's is a "
        "third rewrite. `templates/common/events/arsfest_base.html` is the shared "
        "page and sf already extends it; moving date, pulterit and biocum onto it "
        "changes what visitors see, so it belongs in its own change."
    ),
    "date/components/scripts.html": (
        "The dad-joke fetcher. Date guards it on `#joke-string` while pulterit runs "
        "it on every page, so the two copies differ in behaviour and not only in "
        "layout. Unifying them is a behaviour change and needs its own decision."
    ),
}


def normalise(path: Path) -> list[str]:
    """Return the template's non-blank lines with their indentation removed."""
    return [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


BLOCK_BODY = re.compile(r"\{%\s*block\s+\w+\s*%\}.*?\{%\s*endblock\s*\w*\s*%\}", re.S)
COMMENT_BODY = re.compile(r"\{%\s*comment\s*%\}.*?\{%\s*endcomment\s*%\}", re.S)
TEMPLATE_PREAMBLE = re.compile(r"\{%\s*(?:extends|load)\s+[^%]*%\}")


def is_pure_override(path: Path) -> bool:
    """True when the file renders nothing but the blocks it fills.

    Such a file has no page body of its own, so two of them resembling each other is
    the pattern this repository wants and not a copy. A pasted page keeps its markup
    outside blocks, which is what the ratchet is looking for.
    """
    text = path.read_text(encoding="utf-8")
    text = BLOCK_BODY.sub("", text)
    text = COMMENT_BODY.sub("", text)
    text = TEMPLATE_PREAMBLE.sub("", text)
    return not text.strip()


def copies_by_path() -> dict[str, dict[str, Path]]:
    """Return ``{logical path: {owner: file}}`` for the shared and association trees."""
    found: dict[str, dict[str, Path]] = {}
    for owner in (SHARED, *ASSOCIATIONS):
        root = TEMPLATES_DIR / owner
        for path in root.rglob("*.html"):
            found.setdefault(path.relative_to(root).as_posix(), {})[owner] = path
    return found


def near_copy_pairs() -> list[dict[str, Any]]:
    """Return every pair of copies that is alike enough to be one pasted component.

    Each entry carries the logical path, the two owners, the similarity ratio and
    the line counts, sorted by path and then by owner so a regenerated baseline is
    stable.
    """
    pairs: list[dict[str, Any]] = []
    for relative, owners in sorted(copies_by_path().items()):
        names = sorted(owners)
        for index, first in enumerate(names):
            for second in names[index + 1 :]:
                if is_pure_override(owners[first]) or is_pure_override(owners[second]):
                    continue
                one, other = normalise(owners[first]), normalise(owners[second])
                if min(len(one), len(other)) < MIN_LINES:
                    continue
                ratio = difflib.SequenceMatcher(None, one, other).ratio()
                if ratio >= THRESHOLD:
                    pairs.append(
                        {
                            "path": relative,
                            "variants": [first, second],
                            "ratio": round(ratio, 4),
                            "lines": [len(one), len(other)],
                        }
                    )
    return pairs


def build_baseline() -> dict[str, Any]:
    """Return the frozen baseline for the templates that are alike today."""
    frozen = near_copy_pairs()
    missing = sorted({pair["path"] for pair in frozen} - REASONS.keys())
    if missing:
        raise SystemExit("every frozen path needs a reason in REASONS; missing: " + ", ".join(missing))
    for pair in frozen:
        pair["reason"] = REASONS[pair["path"]]
    return {"threshold": THRESHOLD, "min_lines": MIN_LINES, "near_copies": frozen}


def write_baseline() -> dict[str, Any]:
    """Write the frozen baseline next to this module and return what was written."""
    data = build_baseline()
    BASELINE_PATH.write_text(json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    return data


def load_baseline() -> dict[str, Any]:
    """Return the frozen baseline, or fail with a pointer to the regeneration command."""
    if not BASELINE_PATH.is_file():
        raise AssertionError(f"{BASELINE_PATH.name} is missing; run the command in the module docstring")
    data = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or "near_copies" not in data:
        raise AssertionError(f"{BASELINE_PATH.name} must hold an object with a 'near_copies' list")
    return data


def frozen_pairs() -> dict[tuple[str, str, str], float]:
    """Return the frozen pairs keyed by ``(path, first, second)`` with the frozen ratio."""
    return {(entry["path"], *entry["variants"]): float(entry["ratio"]) for entry in load_baseline()["near_copies"]}


class TemplateNearCopyTests(SimpleTestCase):
    def test_no_unrecorded_near_copy(self):
        frozen = frozen_pairs()
        offenders = []
        for pair in near_copy_pairs():
            key = (pair["path"], *pair["variants"])
            if key not in frozen:
                offenders.append(
                    f"{pair['path']}: {pair['variants'][0]} and {pair['variants'][1]} are "
                    f"{pair['ratio']:.3f} alike over {pair['lines'][0]} and {pair['lines'][1]} lines"
                )
        self.assertEqual(
            offenders,
            [],
            "A variant template became a copy of another one. Share the component and "
            "override a block, or record the pair with a reason and regenerate the baseline",
        )

    def test_the_baseline_has_no_stale_entry(self):
        observed = {(pair["path"], *pair["variants"]) for pair in near_copy_pairs()}
        stale = sorted(key for key in frozen_pairs() if key not in observed)
        self.assertEqual(
            stale,
            [],
            "These pairs are no longer alike, so the baseline records a copy that no "
            "longer exists; regenerate it so the frozen set stays honest",
        )

    def test_a_frozen_pair_does_not_drift_closer(self):
        frozen = frozen_pairs()
        offenders = []
        for pair in near_copy_pairs():
            key = (pair["path"], *pair["variants"])
            allowed = frozen.get(key)
            if allowed is not None and pair["ratio"] > allowed + DRIFT_MARGIN:
                offenders.append(
                    f"{pair['path']}: {key[1]} and {key[2]} went from {allowed:.3f} to {pair['ratio']:.3f} alike"
                )
        self.assertEqual(
            offenders,
            [],
            "A frozen copy got closer to the template it was copied from; fix the copy "
            "rather than widening the exception",
        )


def main() -> int:
    if sys.argv[1:] != ["--write-baseline"]:
        print(__doc__)
        return 2
    data = write_baseline()
    print(
        f"wrote {BASELINE_PATH.relative_to(BASE_DIR).as_posix()}: "
        f"{len(data['near_copies'])} frozen near-copy pairs over "
        f"{len({pair['path'] for pair in data['near_copies']})} paths"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
