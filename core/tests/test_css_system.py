"""Stylesheet footgun guards for the project's hand-written CSS.

The project ships around ninety hand-written stylesheets and has no CSS linter,
so the test suite is the only thing standing between a maintainer and a new
footgun. ``core/tests/test_static_css.py`` already covers unscoped ``nav``
selectors and the pagination sheet. This module adds the rest of the rules as
ratchets: every rule freezes the state that is in the tree today in
``core/tests/css_footgun_baseline.json`` and fails only when a stylesheet makes
things worse. A ratchet does not fail because someone cleaned something up, so
the tree can be repaired without touching this file. The one exception is the
undefined custom property rule below, which is an exact match in both directions
on purpose.

Regenerate the baseline with::

    uv run python -m core.tests.test_css_system --write-baseline

Run that only to record an intentional, reviewed decision: a breakpoint added to
the documented scale, an ``!important`` that a maintainer consciously accepted, a
rule removed. Regenerating is never a way to silence an accidental regression. If
a ratchet fails, fix the stylesheet; rewriting the baseline instead turns the
guard into a rubber stamp. The file is written with sorted keys, sorted lists and
a stable two space indent so the diff of an intentional change stays reviewable.
The near-copy section is the one section a regeneration cannot silently extend: a
pair at or above ``THRESHOLD`` with no reason line in ``NEAR_DUPLICATE_REASONS``
stops the regenerator instead of being recorded.

Static resolution, which the undefined token rule depends on: a page's
stylesheets come from the association's own directory first and
``static/common/`` second (``build_static_dirs`` in ``core/settings/common.py``).
A file at the same logical path under ``static/<variant>/`` therefore REPLACES
the shared file, it does not extend it, and the guard models that per variant.

Rules:

1. No undefined custom property, per variant. Exact match against
   ``KNOWN_UNDEFINED``, so it fails when a new gap appears and also when a fixed
   gap is left in the mapping.
2. ``!important`` ratchet, per file.
3. ``z-index`` ratchet, per file.
4. ``@media`` breakpoint ratchet, one global set of normalised query strings.
5. No pointless shadow stylesheet that is byte-identical to the shared file at
   the same logical path.
6. No zero-byte stylesheet that a template actually links (a one way ratchet,
   see ``EmptyStylesheetTests``).
7. No near-copy shadow stylesheet, per variant: a variant sheet at least
   ``THRESHOLD`` similar to the shared sheet at the same logical path is a fork
   rather than a delta, and a frozen pair must not drift further towards the
   shared sheet (see ``NearDuplicateShadowTests``).

Rule 7 is the other half of rule 5. A shadow that is byte-identical is dead
weight; a shadow that is nearly identical is worse, because it is a private fork
of the shared rules that keeps rendering its stale copy while the shared sheet
moves on, which is how the two trees actually drift apart. The comparison is on
rules rather than bytes: both files are stripped of ``/* ... */`` comments, every
run of whitespace is collapsed to a single space, the ends are stripped, and
``difflib.SequenceMatcher.ratio()`` scores what is left, so whitespace and
comment differences no longer count. A ratio at or above
``THRESHOLD`` (0.75) means the shadow is three quarters of the shared sheet,
which is a fork rather than a delta, so it either has to be deleted, with the
difference expressed as palette tokens, or split into a shared core sheet plus a
small association delta. Both routes are documented in ``docs/dev/css.md`` under
the legitimate ways to vary an association. A pair that is already frozen fails
as soon as its ratio rises by more than ``DRIFT_MARGIN`` (0.02) above the frozen
value, because that is the fork drifting further instead of being reduced. Only
the variants in ``VARIANTS`` are walked, and a variant sheet whose logical path
has no ``static/common/`` counterpart is not a shadow at all, so it is never
considered.

``*.min.css`` and anything under a ``vendor`` directory are skipped everywhere,
exactly as ``core/tests/test_static_css.py`` does: generated and third-party
sheets are not ours to police.
"""

import difflib
import json
import re
import sys
import tempfile
from collections.abc import Iterable, Iterator, Mapping
from pathlib import Path
from typing import Any

from django.test import SimpleTestCase

BASE_DIR = Path(__file__).resolve().parents[2]
STATIC_DIR = BASE_DIR / "static"
TEMPLATES_DIR = BASE_DIR / "templates"
BASELINE_PATH = Path(__file__).resolve().with_name("css_footgun_baseline.json")

# Associations that ship their own stylesheet tree. Keep this in step with
# ``build_static_dirs`` callers in core/settings/.
VARIANTS = ("date", "kk", "biocum", "pulterit", "sf", "impuls")

COMMENT = re.compile(r"/\*.*?\*/", re.S)
IMPORTANT = re.compile(r"!\s*important", re.I)
MEDIA_PRELUDE = re.compile(r"@media([^{]*)\{")
VAR_CALL = re.compile(r"var\(")
STATIC_TAG = re.compile(r"""\{%\s*static\s+['"]([^'"]+)['"]""")
STATIC_LITERAL = re.compile(r"""['"](/static/[^'"]+)['"]""")

# Custom properties that are legitimately provided from outside the stylesheet
# tree. Each name carries its provider. A trailing ``*`` means a prefix family.
EXTERNAL_CUSTOM_PROPERTIES = {
    # Django admin's theme, injected by django.contrib.admin's base template.
    "--body-bg": "Django admin",
    "--body-fg": "Django admin",
    "--body-quiet-color": "Django admin",
    "--darkened-bg": "Django admin",
    "--border-color": "Django admin",
    "--primary": "Django admin",
    "--primary-fg": "Django admin",
    "--hairline-color": "Django admin",
    "--link-fg": "Django admin",
    # django-unfold's theme family, only injected when USE_UNFOLD is on.
    "--color-*": "django-unfold, only when USE_UNFOLD=True",
    # Bootstrap's own custom properties.
    "--bs-*": "Bootstrap",
    # No provider needed: every use site passes a literal fallback.
    "--border-radius": "literal fallback at every use site",
}

# (variant, token) -> why the gap is tolerated. The undefined token test asserts
# that the set of observed offenders EQUALS this mapping, so it fails when a new
# gap appears and when a gap that was fixed is left in the mapping. Removing an
# entry is a one-line change: delete the line once the stylesheet declares the
# token. Listed here rather than in an allowlist of definitions because these are
# real bugs, not sanctioned providers.
#
# A gap whose every consumer passes a fallback is not an offender and must not be
# listed here, because no declaration is dropped.
KNOWN_UNDEFINED: dict[tuple[str, str], str] = {
    (
        "date",
        "--luciaBackgroundColor",
    ): "only static/kk/date/css/date-root.css declares it, and lucia is installed for kk only",
    (
        "biocum",
        "--luciaBackgroundColor",
    ): "only static/kk/date/css/date-root.css declares it, and lucia is installed for kk only",
    (
        "pulterit",
        "--luciaBackgroundColor",
    ): "only static/kk/date/css/date-root.css declares it, and lucia is installed for kk only",
    (
        "sf",
        "--luciaBackgroundColor",
    ): "only static/kk/date/css/date-root.css declares it, and lucia is installed for kk only",
    (
        "impuls",
        "--luciaBackgroundColor",
    ): "only static/kk/date/css/date-root.css declares it, and lucia is installed for kk only",
}

# Shadows that are byte-identical to the shared stylesheet today. The list is
# allowed to be empty, and it must stay a list of offenders only: an empty list
# means no variant stylesheet duplicates the shared file at the same logical
# path, which is the state the tree is in now that the biocum copies are gone.
KNOWN_DUPLICATE_SHADOWS: tuple[str, ...] = ()

# Ratio of shared to association text at which a shadow stops being a delta and
# becomes a fork. Three quarters of the shared sheet means the association is
# keeping its own stale copy of rules the shared sheet owns, so the fix is to
# delete the shadow (expressing the difference as palette tokens) or to split it
# into a shared core sheet plus a small association delta. See rule 7 in the
# module docstring and the legitimate ways to vary an association in
# docs/dev/css.md.
THRESHOLD = 0.75

# A frozen near-copy is allowed to move by this much before it counts as drift.
# The margin absorbs whitespace and comment level noise that the normalisation
# already removes, so only a real move towards the shared sheet trips the ratchet.
DRIFT_MARGIN = 0.02

# Near-copy shadows frozen in the baseline, keyed as the baseline keys them. The
# reason is carried into the baseline by the regeneration path, and the
# regenerator refuses to record a near copy that has no line here: a new fork is
# either fixed as the docstring describes or justified in a review of this file.
NEAR_DUPLICATE_REASONS: dict[str, str] = {
    "biocum: core/css/footer.css": (
        "the biocum footer rewrites the footer image sizing, drops the shared partner link rules and adds an invert "
        "filter; delete it or split it into a shared core sheet plus a small biocum delta"
    ),
    "kk: events/css/tomtejakt.css": (
        "the kk tomtejakt sheet is a copy of the shared sheet that never got the event-association-logo rule the "
        "shared sheet gained, which is exactly the drift the rule exists to stop"
    ),
    "sf: core/css/footer.css": (
        "the sf footer replaces the footer image sizing, drops the shared partner link rules and adds its own social "
        "link rules; delete it or split it into a shared core sheet plus a small sf delta"
    ),
    "sf: events/css/detail.css": (
        "the sf event detail sheet differs from the shared sheet only in whitespace and one hover background token, "
        "so the fix is to delete it and move that color into the sf palette"
    ),
}


def project_stylesheets(root: Path) -> list[Path]:
    """Return the hand-written stylesheets under a directory, sorted by path.

    ``*.min.css`` and anything inside a ``vendor`` directory are skipped, as in
    ``core/tests/test_static_css.py``.
    """
    return sorted(
        path for path in root.rglob("*.css") if not path.name.endswith(".min.css") and "vendor" not in path.parts
    )


def strip_comments(css: str) -> str:
    """Remove ``/* ... */`` comments, so commented-out rules are not scanned."""
    return COMMENT.sub("", css)


def _declaration(selector: str, pending: list[str]) -> tuple[str, str, str] | None:
    """Build one ``(selector, property, value)`` triple, or None without a colon."""
    text = "".join(pending).strip()
    if ":" not in text:
        return None
    prop, _, value = text.partition(":")
    return selector, prop.strip(), value.strip()


def iter_declarations(css: str) -> Iterator[tuple[str, str, str]]:
    """Yield ``(selector, property, value)`` for every declaration in a stylesheet.

    ``selector`` is the nearest enclosing selector, or an empty string inside an
    at-rule that has no parent rule, such as ``@font-face``. Braces, semicolons
    and colons inside strings or parentheses are not structure, which is what
    keeps the Google Fonts imports (their URLs contain a semicolon) and nested
    rules from being split in the wrong place.
    """
    stack: list[str] = []
    selector = ""
    pending: list[str] = []
    depth = 0
    quote = ""
    for char in strip_comments(css):
        if quote:
            pending.append(char)
            if char == quote:
                quote = ""
        elif char in "\"'":
            quote = char
            pending.append(char)
        elif char in "([":
            depth += 1
            pending.append(char)
        elif char in ")]":
            depth = max(0, depth - 1)
            pending.append(char)
        elif depth == 0 and char == "{":
            prelude = " ".join("".join(pending).split())
            pending = []
            stack.append(selector)
            if not prelude.startswith("@"):
                selector = prelude
        elif depth == 0 and char == "}":
            found = _declaration(selector, pending)
            pending = []
            if found:
                yield found
            if stack:
                selector = stack.pop()
        elif depth == 0 and char == ";":
            found = _declaration(selector, pending)
            pending = []
            if found:
                yield found
        else:
            pending.append(char)


def important_count(css: str) -> int:
    """Count ``!important`` occurrences, ignoring those inside comments."""
    return len(IMPORTANT.findall(strip_comments(css)))


def z_index_declarations(css: str) -> list[tuple[str, str]]:
    """Return ``(value, selector)`` for every ``z-index`` declaration, in source order."""
    return [(value, selector) for selector, prop, value in iter_declarations(css) if prop.lower() == "z-index"]


def media_query_preludes(css: str) -> list[str]:
    """Return the raw ``@media`` query strings, with runs of whitespace collapsed."""
    return [" ".join(match.group(1).split()) for match in MEDIA_PRELUDE.finditer(strip_comments(css))]


def normalise_media_query(query: str) -> str:
    """Return the breakpoint key for a media query.

    Only whitespace is normalised: runs of spaces, around a colon, and around a
    comma. The raw whitespace variants such as ``(max-width : 992px)`` are
    tolerated for now, so they share a key with ``(max-width: 992px)`` instead of
    showing up as a brand new breakpoint. Normalising more (unit spelling,
    ``only screen`` against an implicit ``all``) would start rewriting what the
    author meant, so the ratchet stops at whitespace.
    """
    normalised = " ".join(query.split())
    normalised = re.sub(r"\s*:\s*", ": ", normalised)
    return re.sub(r"\s*,\s*", ", ", normalised)


def custom_property_definitions(css: str) -> set[str]:
    """Return every ``--token`` a stylesheet declares."""
    return {prop for _, prop, _ in iter_declarations(css) if prop.startswith("--")}


def has_top_level_comma(arguments: str) -> bool:
    """Return True when a ``var()`` argument list carries a fallback.

    A top level comma is the fallback separator; a comma nested inside another
    ``var()`` belongs to that inner call.
    """
    depth = 0
    for char in arguments:
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
        elif char == "," and depth == 0:
            return True
    return False


def var_references(css: str) -> list[tuple[str, bool]]:
    """Return ``(token, has_fallback)`` for every ``var()`` call, nested ones included.

    ``var(--a, var(--b))`` yields ``(--a, True)`` and ``(--b, False)``: a
    reference inside a fallback chain is still a real reference, so the nested
    call has to be visited on its own terms rather than read as part of the outer
    declaration.
    """
    text = strip_comments(css)
    references: list[tuple[str, bool]] = []
    for match in VAR_CALL.finditer(text):
        depth = 1
        index = match.end()
        while index < len(text) and depth:
            if text[index] == "(":
                depth += 1
            elif text[index] == ")":
                depth -= 1
            index += 1
        arguments = text[match.end() : index - 1]
        references.append((arguments.split(",")[0].strip(), has_top_level_comma(arguments)))
    return references


def is_external(token: str) -> bool:
    """Return True when the external allowlist names the token or its prefix family."""
    for name in EXTERNAL_CUSTOM_PROPERTIES:
        if name.endswith("*"):
            if token.startswith(name[:-1]):
                return True
        elif token == name:
            return True
    return False


def effective_stylesheets(root: Path, variant: str) -> dict[Path, Path]:
    """Return the stylesheet set a variant can load, keyed by logical path.

    The variant's own directory wins over ``static/common/``, matching
    ``build_static_dirs``: a file at the same logical path replaces the shared
    file rather than extending it.
    """
    variant_root = root / "static" / variant
    shared_root = root / "static" / "common"
    files = {path.relative_to(shared_root): path for path in project_stylesheets(shared_root)}
    files.update({path.relative_to(variant_root): path for path in project_stylesheets(variant_root)})
    return files


def undefined_custom_properties(root: Path) -> dict[tuple[str, str], list[str]]:
    """Return ``{(variant, token): [offending files]}`` for the undefined tokens.

    A reference counts as undefined when the ``var()`` call has no fallback and
    the token is declared neither anywhere in that variant's effective stylesheet
    set nor by the external allowlist.
    """
    offenders: dict[tuple[str, str], list[str]] = {}
    for variant in VARIANTS:
        stylesheets = effective_stylesheets(root, variant)
        texts = {path: path.read_text(encoding="utf-8") for path in stylesheets.values()}
        defined = {token for text in texts.values() for token in custom_property_definitions(text)}
        defined.update(name for name in EXTERNAL_CUSTOM_PROPERTIES if not name.endswith("*"))
        for path, text in sorted(texts.items(), key=lambda item: item[0].as_posix()):
            for token, has_fallback in var_references(text):
                if has_fallback or not token.startswith("--") or is_external(token) or token in defined:
                    continue
                offenders.setdefault((variant, token), []).append(path.relative_to(root).as_posix())
    return {key: sorted(set(files)) for key, files in offenders.items()}


def identical_shadow_files(root: Path) -> list[str]:
    """Return the shadow stylesheets that are byte-identical to the shared file.

    Only the in scope variants (``VARIANTS``) are walked. A variant file is a
    shadow when ``static/common/`` holds a file at the same logical path and the
    two are byte for byte the same, which makes the override pure dead weight.
    """
    duplicates: list[str] = []
    for variant in VARIANTS:
        variant_root = root / "static" / variant
        for path in project_stylesheets(variant_root):
            shared = root / "static" / "common" / path.relative_to(variant_root)
            if shared.is_file() and path.read_bytes() == shared.read_bytes():
                duplicates.append(path.relative_to(root).as_posix())
    return sorted(duplicates)


def new_shadow_offenders(root: Path, known: Iterable[str] = ()) -> list[str]:
    """Return identical shadows that the known list does not cover yet."""
    allowed = set(known)
    return [relative for relative in identical_shadow_files(root) if relative not in allowed]


def normalise_stylesheet(css: str) -> str:
    """Return the rule text of a stylesheet, with comments and formatting removed.

    Comments are stripped, every run of whitespace collapses to one space and the
    ends are stripped, so two sheets that differ only in whitespace runs or
    commentary compare as equal and the similarity score is about rules.
    """
    return " ".join(strip_comments(css).split())


def shadow_similarity(shared: Path, association: Path) -> float:
    """Return the ``difflib`` ratio between the normalised shared and shadow text.

    ``1.0`` is a rule for rule copy, ``0.0`` is nothing in common. The scan reads
    the same normalised text that ``NearDuplicateShadowTests`` reasons about, so
    the number in a failure message is reproducible by hand.
    """
    return difflib.SequenceMatcher(
        None,
        normalise_stylesheet(shared.read_text(encoding="utf-8")),
        normalise_stylesheet(association.read_text(encoding="utf-8")),
    ).ratio()


def shadow_key(variant: str, relative: Path) -> str:
    """Return the baseline key for a shadow, ``"<variant>: <logical path>"``."""
    return f"{variant}: {relative.as_posix()}"


def shadow_pairs(root: Path) -> dict[str, float]:
    """Return ``{key: ratio}`` for every in scope variant sheet that shadows a shared sheet.

    A variant sheet is a shadow only when ``static/common/`` holds a file at the
    same logical path. A variant sheet with no shared counterpart is not a shadow
    and is not returned, which keeps it out of the near-copy rule entirely.
    """
    ratios: dict[str, float] = {}
    for variant in VARIANTS:
        variant_root = root / "static" / variant
        for path in project_stylesheets(variant_root):
            relative = path.relative_to(variant_root)
            shared = root / "static" / "common" / relative
            if shared.is_file():
                ratios[shadow_key(variant, relative)] = shadow_similarity(shared, path)
    return ratios


def near_duplicate_shadows(root: Path) -> dict[str, float]:
    """Return the shadow pairs at or above ``THRESHOLD``, keyed by shadow key."""
    return {key: ratio for key, ratio in shadow_pairs(root).items() if ratio >= THRESHOLD}


def near_duplicate_offenders(root: Path, frozen: Mapping[str, float]) -> list[str]:
    """Return the near-copy shadows the frozen list does not cover yet."""
    offenders: list[str] = []
    for key, ratio in sorted(near_duplicate_shadows(root).items()):
        if key in frozen:
            continue
        variant, _, relative = key.partition(": ")
        offenders.append(
            f"static/{variant}/{relative}: ratio {ratio:.3f} against static/common/{relative} "
            f"(threshold {THRESHOLD}), so it is a fork of the shared sheet rather than a delta"
        )
    return offenders


def drifted_shadow_offenders(root: Path, frozen: Mapping[str, float]) -> list[str]:
    """Return the frozen near-copies that moved further towards the shared sheet.

    A pair that is gone, or that fell below its frozen ratio, is not a failure:
    a ratchet never fails because someone cleaned something up. Only the pairs
    that exist and rose by more than ``DRIFT_MARGIN`` are reported.
    """
    observed = shadow_pairs(root)
    offenders: list[str] = []
    for key, frozen_ratio in sorted(frozen.items()):
        ratio = observed.get(key)
        if ratio is None or ratio <= frozen_ratio + DRIFT_MARGIN:
            continue
        variant, _, relative = key.partition(": ")
        offenders.append(
            f"static/{variant}/{relative}: frozen ratio {frozen_ratio:.3f}, now {ratio:.3f} "
            f"(more than {DRIFT_MARGIN} above the frozen value), so the fork drifted further instead of shrinking"
        )
    return offenders


def zero_byte_stylesheets(paths: Iterable[Path]) -> list[Path]:
    """Return the stylesheets that hold no bytes at all."""
    return [path for path in paths if path.stat().st_size == 0]


def static_logical_path(path: Path, root: Path) -> Path:
    """Return a stylesheet's logical static path, the one a template writes.

    Every tree under ``static/`` is one entry of STATICFILES_DIRS, so a file is
    addressed from its own tree: ``static/common/news/css/article.css`` is
    ``news/css/article.css`` in a template, and ``static/kk/core/css/base.css``
    is ``core/css/base.css``.
    """
    static_root = root / "static"
    relative = path.relative_to(static_root)
    if len(relative.parts) > 1 and (static_root / relative.parts[0]).is_dir():
        return Path(*relative.parts[1:])
    return relative


def template_static_references(root: Path) -> set[str]:
    """Return the static paths templates link, as static-relative paths.

    Only literal forms are picked up: ``{% static 'polls/css/style.css' %}`` and a
    quoted ``/static/...`` string. A path composed at runtime is invisible here,
    which is why the zero-byte rule only ever fails on a path this scan sees.
    """
    references: set[str] = set()
    for path in sorted(root.rglob("*.html")):
        text = path.read_text(encoding="utf-8")
        references.update(match.group(1) for match in STATIC_TAG.finditer(text))
        references.update(match.group(1).removeprefix("/static/") for match in STATIC_LITERAL.finditer(text))
    return references


def build_baseline(root: Path = BASE_DIR) -> dict[str, Any]:
    """Build the frozen baseline from the tree as it is right now.

    Sparse on purpose: a file with no ``!important`` and no ``z-index`` is absent
    from its mapping, and absence means zero. That keeps the file small, and it
    keeps a regenerated diff readable.
    """
    stylesheets = project_stylesheets(root / "static")
    important_counts: dict[str, int] = {}
    z_index_values: dict[str, list[str]] = {}
    media_queries: set[str] = set()
    for path in stylesheets:
        text = path.read_text(encoding="utf-8")
        relative = path.relative_to(root).as_posix()
        count = important_count(text)
        if count:
            important_counts[relative] = count
        values = sorted({value for value, _ in z_index_declarations(text)})
        if values:
            z_index_values[relative] = values
        media_queries.update(
            normalise_media_query(prelude) for prelude in media_query_preludes(text) if is_breakpoint_query(prelude)
        )
    linked = template_static_references(root / "templates")
    empty_linked = sorted(
        path.relative_to(root).as_posix()
        for path in zero_byte_stylesheets(stylesheets)
        if static_logical_path(path, root).as_posix() in linked
    )
    observed_near_duplicates = near_duplicate_shadows(root)
    unlisted = sorted(key for key in observed_near_duplicates if key not in NEAR_DUPLICATE_REASONS)
    if unlisted:
        raise AssertionError(
            "near-copy shadow stylesheets have no frozen reason: "
            + ", ".join(unlisted)
            + "; fix the stylesheet as docs/dev/css.md describes, or add one reason line per pair to "
            "NEAR_DUPLICATE_REASONS in core/tests/test_css_system.py"
        )
    near_duplicates = {
        key: {"ratio": round(ratio, 4), "reason": NEAR_DUPLICATE_REASONS[key]}
        for key, ratio in sorted(observed_near_duplicates.items())
    }
    return {
        "important_counts": important_counts,
        "media_queries": sorted(media_queries),
        "near_duplicate_shadows": near_duplicates,
        "z_index_values": z_index_values,
        "zero_byte_stylesheets_linked": empty_linked,
    }


def write_baseline() -> dict[str, Any]:
    """Write the frozen baseline next to this module and return what was written."""
    data = build_baseline()
    text = json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    BASELINE_PATH.write_text(text, encoding="utf-8")
    return data


def load_baseline() -> dict[str, Any]:
    """Return the frozen baseline, or fail with a pointer to the regeneration command."""
    if not BASELINE_PATH.is_file():
        raise AssertionError(f"{BASELINE_PATH.name} is missing; run the command in the module docstring")
    data = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise AssertionError(f"{BASELINE_PATH.name} must hold a JSON object")
    return data


def baseline_section(key: str) -> Any:
    """Return one baseline section, failing loudly when the file lacks it."""
    baseline = load_baseline()
    if key not in baseline:
        raise AssertionError(
            f"{BASELINE_PATH.name} has no {key!r} section; regenerate it with the command in the module docstring"
        )
    return baseline[key]


def frozen_near_duplicate_ratios() -> dict[str, float]:
    """Return the frozen near-copy ratios as ``{key: ratio}``, dropping the reasons."""
    return {key: entry["ratio"] for key, entry in baseline_section("near_duplicate_shadows").items()}


class DeclarationScannerTests(SimpleTestCase):
    def test_declarations_carry_the_nearest_selector(self):
        declarations = list(iter_declarations("@media (min-width: 1px) { .a { color: red; } }"))
        self.assertEqual(declarations, [(".a", "color", "red")])
        self.assertEqual(list(iter_declarations(".a { .b { color: red; } }")), [(".b", "color", "red")])
        self.assertEqual(list(iter_declarations("@font-face { src: url(x.woff2); }")), [("", "src", "url(x.woff2)")])

    def test_semicolons_inside_strings_and_urls_do_not_split_declarations(self):
        css = "a { background: url('data:x;y'); color: red; }"
        self.assertEqual(
            list(iter_declarations(css)),
            [("a", "background", "url('data:x;y')"), ("a", "color", "red")],
        )

    def test_a_final_declaration_without_a_semicolon_is_still_read(self):
        self.assertEqual(list(iter_declarations(".a { z-index: 5 }")), [(".a", "z-index", "5")])


class CustomPropertyScannerTests(SimpleTestCase):
    def test_definitions_are_read_from_declarations_only(self):
        self.assertEqual(custom_property_definitions(":root { --a: 1; }"), {"--a"})
        self.assertEqual(custom_property_definitions(".block--modifier:hover { color: red; }"), set())
        self.assertEqual(custom_property_definitions("/* --a: 1; */"), set())

    def test_references_report_whether_a_fallback_is_present(self):
        self.assertEqual(var_references("a { color: var(--a); }"), [("--a", False)])
        self.assertEqual(var_references("a { color: var( --a ); }"), [("--a", False)])
        self.assertEqual(var_references("a { color: var(--a, red); }"), [("--a", True)])

    def test_references_inside_a_fallback_chain_are_real_references(self):
        self.assertEqual(var_references("a { --x: var(--a, var(--b)); }"), [("--a", True), ("--b", False)])
        self.assertEqual(var_references("a { --x: var(--a, var(--b, red)); }"), [("--a", True), ("--b", True)])
        self.assertTrue(has_top_level_comma("--a, red"))
        self.assertTrue(has_top_level_comma("--a, var(--b, red)"))
        self.assertFalse(has_top_level_comma("--a"))
        self.assertFalse(has_top_level_comma("--a-no-comma"))

    def test_external_allowlist_matches_names_and_families(self):
        self.assertTrue(is_external("--body-fg"))
        self.assertTrue(is_external("--bs-grid-gap"))
        self.assertTrue(is_external("--color-base-100"))
        self.assertFalse(is_external("--silver"))
        self.assertFalse(is_external("--colorTextMedium"))


class UndefinedCustomPropertyTests(SimpleTestCase):
    def _tree(self, root: Path, files: dict[str, str]) -> Path:
        for relative, text in files.items():
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        return root

    def test_observed_offenders_equal_the_known_mapping(self):
        observed = undefined_custom_properties(BASE_DIR)
        new_offenders = sorted(
            f"{variant}: {files[0]}: {token}"
            for (variant, token), files in observed.items()
            if (variant, token) not in KNOWN_UNDEFINED
        )
        stale_entries = sorted(
            f"{variant}: {token}" for (variant, token) in KNOWN_UNDEFINED if (variant, token) not in observed
        )

        self.assertEqual(
            new_offenders,
            [],
            "New undefined custom properties. Declare the token or add a fallback at the use site; do not list it here",
        )
        self.assertEqual(
            stale_entries,
            [],
            "KNOWN_UNDEFINED lists a gap that is no longer observed. Delete that one line from the mapping",
        )

    def test_scan_flags_a_missing_token_and_honours_the_variant_override(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            self._tree(
                root,
                {
                    "static/common/app/css/a.css": "a { color: var(--nope); }\n",
                    "static/kk/app/css/a.css": "a { color: var(--nope, red); }\n",
                },
            )
            offenders = undefined_custom_properties(root)

        self.assertEqual(set(offenders), {(variant, "--nope") for variant in VARIANTS if variant != "kk"})
        self.assertEqual(offenders[("date", "--nope")], ["static/common/app/css/a.css"])

    def test_scan_accepts_external_families_and_fallbacks(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            self._tree(
                root,
                {
                    "static/common/app/css/a.css": (
                        "a { color: var(--bs-body-color); background: var(--body-bg); }\n"
                        "b { color: var(--missing, red); }\n"
                        "c { --local: 1; color: var(--local); }\n"
                    ),
                },
            )
            self.assertEqual(undefined_custom_properties(root), {})


class ImportantRatchetTests(SimpleTestCase):
    def test_no_stylesheet_gains_an_important(self):
        frozen = baseline_section("important_counts")
        offenders = []
        for path in project_stylesheets(STATIC_DIR):
            relative = path.relative_to(BASE_DIR).as_posix()
            before = frozen.get(relative, 0)
            after = important_count(path.read_text(encoding="utf-8"))
            if after > before:
                note = "file had none" if before == 0 else f"{before} -> {after}"
                offenders.append(f"{relative}: {note} !important")
        self.assertEqual(offenders, [], "A stylesheet gained !important; add specificity or scope instead")

    def test_scanner_ignores_comments(self):
        self.assertEqual(important_count("a { color: red !important; }"), 1)
        self.assertEqual(important_count("a { color: red ! important; }"), 1)
        self.assertEqual(important_count("/* a { color: red !important; } */"), 0)
        self.assertEqual(important_count("/* !important */\na { color: red !important; }"), 1)


class ZIndexRatchetTests(SimpleTestCase):
    def test_no_stylesheet_invents_a_z_index(self):
        frozen = baseline_section("z_index_values")
        known_everywhere = {value for values in frozen.values() for value in values}
        offenders = []
        for path in project_stylesheets(STATIC_DIR):
            relative = path.relative_to(BASE_DIR).as_posix()
            known_here = set(frozen.get(relative, []))
            for value, selector in z_index_declarations(path.read_text(encoding="utf-8")):
                if value in known_here:
                    continue
                if value in known_everywhere:
                    note = "already used elsewhere, new to this file"
                else:
                    note = "new in the project, add it to the documented scale instead"
                offenders.append(f"{relative}: {selector} {{ z-index: {value} }} ({note})")
        self.assertEqual(offenders, [], "A stylesheet invented a z-index value")

    def test_scanner_reports_the_selector_context(self):
        self.assertEqual(z_index_declarations(".a { z-index: 5; }"), [("5", ".a")])
        self.assertEqual(z_index_declarations("@media (min-width: 1px) { .a { z-index: -1 } }"), [("-1", ".a")])
        self.assertEqual(z_index_declarations(".a { Z-INDEX: 5; }"), [("5", ".a")])


def is_breakpoint_query(query: str) -> bool:
    """True for a media query that actually keys off a viewport width.

    The ratchet exists to keep breakpoints on the Bootstrap scale, so ``@media
    print`` and feature queries such as ``(hover: hover)`` or
    ``(prefers-reduced-motion: reduce)`` are not its business: they are media
    types and feature tests, not widths, and freezing them would flag a print
    stylesheet as a new breakpoint.
    """
    return "width" in normalise_media_query(query).lower()


class BreakpointRatchetTests(SimpleTestCase):
    def test_no_new_breakpoint_query(self):
        frozen = set(baseline_section("media_queries"))
        offenders = []
        for path in project_stylesheets(STATIC_DIR):
            relative = path.relative_to(BASE_DIR).as_posix()
            for prelude in media_query_preludes(path.read_text(encoding="utf-8")):
                if not is_breakpoint_query(prelude):
                    continue
                key = normalise_media_query(prelude)
                if key not in frozen:
                    raw = f" (raw: {prelude})" if prelude != key else ""
                    offenders.append(f"{relative}: @media {key}{raw}")
        self.assertEqual(offenders, [], "A stylesheet introduced a new breakpoint; reuse a documented one")

    def test_media_types_and_feature_queries_are_not_breakpoints(self):
        self.assertFalse(is_breakpoint_query("print"))
        self.assertFalse(is_breakpoint_query("(hover: hover) and (pointer: fine)"))
        self.assertFalse(is_breakpoint_query("(prefers-reduced-motion: reduce)"))
        self.assertTrue(is_breakpoint_query("(max-width: 992px)"))
        self.assertTrue(is_breakpoint_query("only screen and (min-width: 576px)"))

    def test_whitespace_around_the_colon_shares_one_key(self):
        self.assertEqual(normalise_media_query("(max-width : 992px)"), "(max-width: 992px)")
        self.assertEqual(normalise_media_query("(max-width:992px)"), "(max-width: 992px)")
        self.assertEqual(
            normalise_media_query("only screen  and (max-width: 992px), print"),
            "only screen and (max-width: 992px), print",
        )

    def test_commented_out_media_blocks_are_not_queries(self):
        self.assertEqual(media_query_preludes("/* @media (max-width: 1px) { } */"), [])
        self.assertEqual(media_query_preludes("@media (max-width: 1px) { a { color: red; } }"), ["(max-width: 1px)"])


class DuplicateShadowTests(SimpleTestCase):
    def _tree(self, root: Path, files: dict[str, str]) -> Path:
        for relative, text in files.items():
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        return root

    def test_no_pointless_shadow_stylesheet(self):
        offenders = new_shadow_offenders(BASE_DIR, KNOWN_DUPLICATE_SHADOWS)
        self.assertEqual(
            offenders,
            [],
            "A variant stylesheet is byte-identical to the shared one; delete it or make it actually override",
        )

    def test_known_shadow_list_is_empty_safe(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            self._tree(
                root,
                {
                    "static/common/app/css/a.css": "a { color: red; }\n",
                    "static/kk/app/css/a.css": "a { color: red; }\n",
                },
            )
            self.assertEqual(new_shadow_offenders(root, ()), ["static/kk/app/css/a.css"])
            self.assertEqual(new_shadow_offenders(root, ("static/kk/app/css/a.css",)), [])

    def test_an_edited_shadow_is_not_a_duplicate(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            self._tree(
                root,
                {
                    "static/common/app/css/a.css": "a { color: red; }\n",
                    "static/kk/app/css/a.css": "a { color: blue; }\n",
                },
            )
            self.assertEqual(identical_shadow_files(root), [])


class NearDuplicateShadowTests(SimpleTestCase):
    """Rule 7: freeze the near copies that exist and fail on a new one or on drift.

    The frozen list lives in ``near_duplicate_shadows`` in the baseline, one entry
    per pair with the ratio measured when it was accepted and a one line reason.
    The two ratchets read that list; the remaining tests pin the scanner down on a
    temporary tree, because the real tree only holds four pairs.
    """

    def _tree(self, root: Path, files: dict[str, str]) -> Path:
        for relative, text in files.items():
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        return root

    def test_no_new_near_duplicate_shadow(self):
        offenders = near_duplicate_offenders(BASE_DIR, frozen_near_duplicate_ratios())
        self.assertEqual(
            offenders,
            [],
            "A variant stylesheet is a near copy of the shared sheet. Delete it, express the difference as palette "
            "tokens, or split it into a shared core sheet plus a small association delta; docs/dev/css.md documents "
            "both routes",
        )

    def test_frozen_near_duplicates_do_not_drift_further(self):
        offenders = drifted_shadow_offenders(BASE_DIR, frozen_near_duplicate_ratios())
        self.assertEqual(
            offenders,
            [],
            "A frozen near copy moved closer to the shared sheet. Reduce the fork or delete it; do not raise the "
            "frozen ratio",
        )

    def test_whitespace_and_comments_do_not_change_the_ratio(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            shared = "/* shared */\na {\n  color: red;\n}\n\nb   { color: blue; }\n"
            association = "a { color: red; }  /* local tweak */\nb { color: blue; }"
            self._tree(
                root,
                {
                    "static/common/app/css/a.css": shared,
                    "static/kk/app/css/a.css": association,
                },
            )
            shared_path = root / "static/common/app/css/a.css"
            association_path = root / "static/kk/app/css/a.css"
            self.assertEqual(shadow_similarity(shared_path, association_path), 1.0)
            self.assertEqual(near_duplicate_shadows(root), {"kk: app/css/a.css": 1.0})

    def test_a_new_near_copy_is_flagged_and_a_frozen_one_is_allowed(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            self._tree(
                root,
                {
                    "static/common/app/css/a.css": "a { color: red; }\nb { color: blue; }\n",
                    "static/kk/app/css/a.css": "a { color: red; }\nb { color: blue; }\n",
                },
            )
            offenders = near_duplicate_offenders(root, {})
            self.assertEqual(len(offenders), 1)
            self.assertIn("static/kk/app/css/a.css", offenders[0])
            self.assertIn("1.000", offenders[0])
            self.assertEqual(near_duplicate_offenders(root, {"kk: app/css/a.css": 1.0}), [])

    def test_a_pair_below_the_threshold_is_not_a_fork(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            self._tree(
                root,
                {
                    "static/common/app/css/a.css": (
                        ".one { color: red; }\n.two { color: blue; }\n.three { color: green; }\n"
                    ),
                    "static/kk/app/css/a.css": ".unrelated { margin: 0; }\n",
                },
            )
            self.assertEqual(near_duplicate_shadows(root), {})
            self.assertEqual(near_duplicate_offenders(root, {}), [])

    def test_a_variant_sheet_without_a_shared_counterpart_is_out_of_scope(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            self._tree(root, {"static/kk/app/css/a.css": "a { color: red; }\n"})
            self.assertEqual(shadow_pairs(root), {})
            self.assertEqual(near_duplicate_offenders(root, {}), [])

    def test_drift_is_reported_once_the_margin_is_passed(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            self._tree(
                root,
                {
                    "static/common/app/css/a.css": "a { color: red; }\nb { color: blue; }\nc { color: green; }\n",
                    "static/kk/app/css/a.css": "a { color: red; }\nb { color: blue; }\nc { color: teal; }\n",
                },
            )
            key = "kk: app/css/a.css"
            ratio = shadow_similarity(root / "static/common/app/css/a.css", root / "static/kk/app/css/a.css")
            self.assertGreater(ratio, THRESHOLD)
            offenders = drifted_shadow_offenders(root, {key: ratio - 0.05})
            self.assertEqual(len(offenders), 1)
            self.assertIn("static/kk/app/css/a.css", offenders[0])
            self.assertIn("frozen ratio", offenders[0])
            self.assertEqual(drifted_shadow_offenders(root, {key: ratio - 0.01}), [])
            self.assertEqual(drifted_shadow_offenders(root, {key: ratio}), [])
            self.assertEqual(drifted_shadow_offenders(root, {key: ratio + 0.5}), [])

    def test_a_deleted_frozen_pair_is_not_a_drift_failure(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            self._tree(root, {"static/common/app/css/a.css": "a { color: red; }\n"})
            self.assertEqual(drifted_shadow_offenders(root, {"kk: app/css/a.css": 0.1}), [])


class EmptyStylesheetTests(SimpleTestCase):
    """Rule 6, a one way ratchet.

    All five zero-byte stylesheets in the tree are linked from a template, so
    failing on them today would only force a baseline entry that says nothing.
    What the guard does instead: once a template links an empty stylesheet, that
    combination is frozen, and a new one fails. An empty file that nobody links
    is ignored, a file that is filled in or deleted is not a failure, and the
    scan is asserted to survive an empty file rather than crash on it. The
    template scan only sees literal ``{% static %}`` and ``/static/`` paths, so
    the rule stays one way on purpose.
    """

    def test_no_new_zero_byte_stylesheet_linked_from_a_template(self):
        frozen = set(baseline_section("zero_byte_stylesheets_linked"))
        linked = template_static_references(TEMPLATES_DIR)
        offenders = []
        for path in zero_byte_stylesheets(project_stylesheets(STATIC_DIR)):
            relative = path.relative_to(BASE_DIR).as_posix()
            if static_logical_path(path, BASE_DIR).as_posix() in linked and relative not in frozen:
                offenders.append(f"{relative}: empty, but a template links it")
        self.assertEqual(offenders, [], "A template links a zero-byte stylesheet; fill it in or drop the link")

    def test_logical_path_drops_the_tree_component(self):
        self.assertEqual(
            static_logical_path(STATIC_DIR / "common" / "news/css/article.css", BASE_DIR).as_posix(),
            "news/css/article.css",
        )
        self.assertEqual(
            static_logical_path(STATIC_DIR / "kk" / "core/css/base.css", BASE_DIR).as_posix(),
            "core/css/base.css",
        )
        self.assertEqual(static_logical_path(STATIC_DIR / "loose.css", BASE_DIR).as_posix(), "loose.css")

    def test_scanners_survive_an_empty_stylesheet(self):
        for css in ("", "   \n\t\n", "/* only a comment */\n", "@media (max-width: 1px) { }"):
            with self.subTest(css=css):
                self.assertEqual(important_count(css), 0)
                self.assertEqual(list(iter_declarations(css)), [])
                self.assertEqual(z_index_declarations(css), [])
                self.assertEqual(custom_property_definitions(css), set())
                self.assertEqual(var_references(css), [])


class BaselineShapeTests(SimpleTestCase):
    def test_baseline_has_every_section(self):
        baseline = load_baseline()
        self.assertEqual(
            sorted(baseline),
            [
                "important_counts",
                "media_queries",
                "near_duplicate_shadows",
                "z_index_values",
                "zero_byte_stylesheets_linked",
            ],
        )

    def test_baseline_lists_are_sorted_and_unique(self):
        for key in ("media_queries", "zero_byte_stylesheets_linked"):
            values = baseline_section(key)
            self.assertEqual(values, sorted(values), f"{key} must be sorted so the regenerated diff stays reviewable")
            self.assertEqual(len(values), len(set(values)), f"{key} must not repeat a value")
        for values in baseline_section("z_index_values").values():
            self.assertEqual(values, sorted(values), "z_index_values lists must be sorted")
        for key in ("important_counts", "z_index_values", "zero_byte_stylesheets_linked"):
            for path in baseline_section(key):
                self.assertTrue((BASE_DIR / path).is_file(), f"{key} names {path}, which no longer exists")

    def test_near_duplicate_entries_carry_a_ratio_and_a_reason(self):
        for key, entry in baseline_section("near_duplicate_shadows").items():
            variant, separator, relative = key.partition(": ")
            self.assertEqual(separator, ": ", f"{key} must read '<variant>: <logical path>'")
            self.assertIn(variant, VARIANTS, f"{key} names a variant outside VARIANTS")
            self.assertTrue((STATIC_DIR / variant / relative).is_file(), f"{key} names a missing shadow")
            self.assertIsInstance(entry["ratio"], float, f"{key} must freeze a numeric ratio")
            self.assertGreaterEqual(entry["ratio"], THRESHOLD, f"{key} is frozen below THRESHOLD")
            self.assertLessEqual(entry["ratio"], 1.0, f"{key} cannot exceed a ratio of 1.0")
            self.assertTrue(entry["reason"].strip(), f"{key} must carry a one line reason")


def main(argv: list[str] | None = None) -> int:
    """Write the baseline when asked for it, otherwise print usage."""
    arguments = list(sys.argv[1:] if argv is None else argv)
    if arguments != ["--write-baseline"]:
        print("usage: uv run python -m core.tests.test_css_system --write-baseline")
        return 2
    data = write_baseline()
    print(
        f"wrote {BASELINE_PATH.relative_to(BASE_DIR).as_posix()}: "
        f"{len(data['important_counts'])} files with !important, "
        f"{len(data['z_index_values'])} files with z-index, "
        f"{len(data['media_queries'])} media queries, "
        f"{len(data['near_duplicate_shadows'])} frozen near-copy shadows, "
        f"{len(data['zero_byte_stylesheets_linked'])} empty stylesheets linked from a template"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
