#!/usr/bin/env python3
"""
Frontend template/CSS regression diff between two git refs.

Purpose:
- Verify that a refactor (renames, moves, modularization) preserves frontend
  behavior and template/CSS contracts.
- Highlight real drift while suppressing common path-churn noise.

What it analyzes:
- Django templates (default: all `templates/**/*.html`, excluding email
  templates unless `--include-emails` is used).
- Flattened template content by recursively resolving `{% include %}`.
- CSS references loaded via `{% static '...css' %}`.
- Referenced CSS file content (normalized hash).

Default behavior (refactor-friendly):
- Compare `develop` (base) vs `WORKTREE` (target).
- Use declaration-only CSS comparison (selector names ignored).
- Canonicalize known CSS rename mappings so correct old->new static path
  updates do not count as diffs.
- Suppress many add/remove false positives when flattened content was moved or
  extracted.
- Detect moved templates (git rename + content-based fallback).
- Audit CSS file renames and report whether old template refs were migrated,
  unresolved, or dropped.

Primary outputs:
- `CHANGED`: same logical template path but contract changed.
- `MOVED`: template path moved/renamed.
- `ADDED` / `REMOVED`: remaining unmatched paths after suppression.
- `CSS rename audit`: migration correctness for renamed CSS paths.

Machine output:
- `--json` emits a stable JSON payload for CI/report tooling.
"""

from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import re
import sys
import textwrap
from fnmatch import fnmatch
from pathlib import PurePosixPath
from typing import Iterable
from css_contract_diff_lib.io import (
    list_css_renames,
    list_files,
    list_template_renames,
    read_file,
    run_git,
)
from css_contract_diff_lib.models import (
    Colors,
    ComponentContract,
    CssRenameAudit,
    RenameAuditBucket,
    style,
)


DEFAULT_ASSOCIATIONS = ("date", "kk", "on", "demo", "biocum")
DEFAULT_TEMPLATE_GLOBS = (
    "templates/**/*.html",
)
DEFAULT_EXCLUDE_TEMPLATE_GLOBS = (
    "templates/**/emails/*.html",
)

STATIC_RE = re.compile(r"""{%\s*static\s+['"]([^'"]+\.css)['"]\s*%}""")
STATIC_TAG_RE = re.compile(r"""{%\s*static\s+(['"])([^'"]+\.css)\1\s*%}""")
INCLUDE_RE = re.compile(r"""{%\s*include\s+['"]([^'"]+\.html)['"](?:\s+[^%]*)?%}""")
COMMENT_RE = re.compile(r"/\*.*?\*/", re.DOTALL)
WS_RE = re.compile(r"\s+")
DECL_BLOCK_RE = re.compile(r"\{([^{}]+)\}")
DJANGO_COMMENT_RE = re.compile(r"{#.*?#}", re.DOTALL)
TOKEN_RE = re.compile(r"({%.*?%}|{{.*?}}|<[^>]+>)", re.DOTALL)




def matches_globs(path: str, globs: Iterable[str]) -> bool:
    return any(fnmatch(path, pattern) for pattern in globs)


def normalize_css(text: str) -> str:
    no_comments = COMMENT_RE.sub("", text)
    squashed = WS_RE.sub(" ", no_comments)
    squashed = re.sub(r"\s*([{}:;,>+~()])\s*", r"\1", squashed)
    return squashed.strip()


def normalize_template_text(text: str) -> str:
    without_comments = DJANGO_COMMENT_RE.sub("", text)
    squashed = WS_RE.sub(" ", without_comments)
    return squashed.strip()


def canonicalize_css_static_refs(
    text: str, css_ref_canonical_map: dict[str, str]
) -> str:
    if not css_ref_canonical_map:
        return text

    def repl(match: re.Match[str]) -> str:
        quote = match.group(1)
        path = match.group(2)
        canonical = css_ref_canonical_map.get(path, path)
        return f"{{% static {quote}{canonical}{quote} %}}"

    return STATIC_TAG_RE.sub(repl, text)


def format_template_for_diff(text: str, wrap_width: int = 100) -> str:
    without_comments = DJANGO_COMMENT_RE.sub("", text)
    parts = TOKEN_RE.split(without_comments)
    lines: list[str] = []
    for part in parts:
        token = part.strip()
        if not token:
            continue
        if TOKEN_RE.fullmatch(token):
            lines.append(token)
            continue
        normalized_text = WS_RE.sub(" ", token).strip()
        if not normalized_text:
            continue
        wrapped = textwrap.wrap(
            normalized_text,
            width=wrap_width,
            break_long_words=False,
            break_on_hyphens=False,
        )
        lines.extend(wrapped if wrapped else [normalized_text])
    return "\n".join(lines)


def normalize_declaration_only(text: str) -> str:
    css = normalize_css(text)
    blocks: list[str] = []
    for block in DECL_BLOCK_RE.findall(css):
        decls = [d.strip() for d in block.split(";") if d.strip()]
        decls_sorted = sorted(decls)
        blocks.append(";".join(decls_sorted))
    return "|".join(sorted(blocks))


def css_fingerprint(text: str, declaration_only: bool = False) -> str:
    normalized = (
        normalize_declaration_only(text) if declaration_only else normalize_css(text)
    )
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def resolve_component_contract(
    repo: str,
    ref: str,
    template_path: str,
    existing_files: set[str],
    cache: dict[str, str | None],
    declaration_only: bool = False,
    flatten_templates: bool = False,
    diff_wrap_width: int = 100,
    css_ref_canonical_map: dict[str, str] | None = None,
) -> ComponentContract:
    visited: set[str] = set()
    css_paths: set[str] = set()
    template_parts = PurePosixPath(template_path).parts
    association = template_parts[1] if len(template_parts) > 2 and template_parts[0] == "templates" else ""

    def read_cached(path: str) -> str | None:
        if path not in cache:
            cache[path] = read_file(repo, ref, path)
        return cache[path]

    def walk(path: str) -> None:
        if path in visited:
            return
        visited.add(path)
        content = read_cached(path)
        if not content:
            return

        for rel_css in STATIC_RE.findall(content):
            candidates = []
            if association:
                candidates.append((PurePosixPath("static") / association / rel_css).as_posix())
            candidates.append((PurePosixPath("static") / "common" / rel_css).as_posix())
            candidates.append((PurePosixPath("static") / rel_css).as_posix())
            for css_path_str in candidates:
                if css_path_str in existing_files:
                    css_paths.add(css_path_str)
                    break

        for include_rel in INCLUDE_RE.findall(content):
            candidates = []
            if association:
                candidates.append((PurePosixPath("templates") / association / include_rel).as_posix())
            candidates.append((PurePosixPath("templates") / "common" / include_rel).as_posix())
            candidates.append((PurePosixPath("templates") / include_rel).as_posix())
            for include_path_str in candidates:
                if include_path_str in existing_files:
                    walk(include_path_str)
                    break

    def flatten(path: str, stack: set[str]) -> str:
        if path in stack:
            return ""
        content = read_cached(path)
        if not content:
            return ""
        stack_next = set(stack)
        stack_next.add(path)

        def replace_include(match: re.Match[str]) -> str:
            include_rel = match.group(1)
            candidates = []
            if association:
                candidates.append(
                    (PurePosixPath("templates") / association / include_rel).as_posix()
                )
            candidates.append((PurePosixPath("templates") / "common" / include_rel).as_posix())
            candidates.append((PurePosixPath("templates") / include_rel).as_posix())
            for include_path_str in candidates:
                if include_path_str in existing_files:
                    return flatten(include_path_str, stack_next)
            return ""

        return INCLUDE_RE.sub(replace_include, content)

    walk(template_path)

    css_paths_sorted = tuple(sorted(css_paths))
    css_fps = []
    for css_path in css_paths_sorted:
        css_text = read_cached(css_path) or ""
        css_fps.append(css_fingerprint(css_text, declaration_only=declaration_only))

    css_fps_sorted = tuple(sorted(css_fps))
    if flatten_templates:
        flat_text = flatten(template_path, set())
        canonical_map = css_ref_canonical_map or {}
        flat_text_canonical = canonicalize_css_static_refs(flat_text, canonical_map)
        flattened_normalized = normalize_template_text(flat_text_canonical)
        flattened_pretty = format_template_for_diff(flat_text, wrap_width=diff_wrap_width)
        template_fp = hashlib.sha256(flattened_normalized.encode("utf-8")).hexdigest()
    else:
        flattened_normalized = None
        flattened_pretty = None
        template_fp = hashlib.sha256(template_path.encode("utf-8")).hexdigest()

    combined = hashlib.sha256(
        "\n".join((template_fp, *css_fps_sorted)).encode("utf-8")
    ).hexdigest()
    return ComponentContract(
        template_path=template_path,
        css_paths=css_paths_sorted,
        css_fingerprints=css_fps_sorted,
        template_fingerprint=template_fp,
        flattened_normalized=flattened_normalized,
        flattened_pretty=flattened_pretty,
        combined_fingerprint=combined,
    )


def collect_contracts(
    repo: str,
    ref: str,
    associations: Iterable[str],
    template_globs: Iterable[str],
    exclude_template_globs: Iterable[str] = (),
    declaration_only: bool = False,
    flatten_templates: bool = False,
    diff_wrap_width: int = 100,
    css_ref_canonical_map: dict[str, str] | None = None,
) -> dict[str, ComponentContract]:
    files = list_files(repo, ref, "")
    existing_files = set(files)
    cache: dict[str, str | None] = {}

    concrete_globs: list[str] = []
    for association in associations:
        for glob_pattern in template_globs:
            concrete_globs.append(glob_pattern.format(association=association))

    template_files = [
        path
        for path in files
        if path.endswith(".html")
        and matches_globs(path, concrete_globs)
        and not matches_globs(path, exclude_template_globs)
    ]

    contracts: dict[str, ComponentContract] = {}
    for template_path in sorted(template_files):
        contracts[template_path] = resolve_component_contract(
            repo=repo,
            ref=ref,
            template_path=template_path,
            existing_files=existing_files,
            cache=cache,
            declaration_only=declaration_only,
            flatten_templates=flatten_templates,
            diff_wrap_width=diff_wrap_width,
            css_ref_canonical_map=css_ref_canonical_map,
        )
    return contracts


def build_css_ref_canonical_map(
    repo: str, base_ref: str, target_ref: str
) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for old_path, new_path in list_css_renames(repo, base_ref, target_ref):
        old_ref = css_path_to_template_ref(old_path)
        new_ref = css_path_to_template_ref(new_path)
        if not old_ref or not new_ref:
            continue
        mapping[old_ref] = new_ref
        mapping[new_ref] = new_ref
    return mapping


def diff_contracts(
    base: dict[str, ComponentContract],
    target: dict[str, ComponentContract],
    common_only: bool = False,
) -> tuple[list[str], list[str], list[str]]:
    base_keys = set(base)
    target_keys = set(target)
    removed = [] if common_only else sorted(base_keys - target_keys)
    added = [] if common_only else sorted(target_keys - base_keys)

    changed: list[str] = []
    for key in sorted(base_keys & target_keys):
        if base[key].combined_fingerprint != target[key].combined_fingerprint:
            changed.append(key)
    return removed, added, changed


def css_path_to_template_ref(path: str) -> str | None:
    p = PurePosixPath(path)
    parts = p.parts
    if len(parts) < 4 or parts[0] != "static":
        return None
    if parts[1] == "common":
        return PurePosixPath(*parts[2:]).as_posix()
    return PurePosixPath(*parts[2:]).as_posix()


def collect_template_css_refs(repo: str, ref: str) -> dict[str, set[str]]:
    refs: dict[str, set[str]] = {}
    for path in list_files(repo, ref, "templates"):
        if not path.endswith(".html"):
            continue
        content = read_file(repo, ref, path) or ""
        css_refs = set(STATIC_RE.findall(content))
        refs[path] = css_refs
    return refs


def template_scope_key(path: str) -> tuple[str, str] | None:
    parts = PurePosixPath(path).parts
    if len(parts) < 3 or parts[0] != "templates":
        return None
    return parts[1], parts[-1]


def audit_css_rename_refs(
    repo: str, base_ref: str, target_ref: str
) -> list[CssRenameAudit]:
    renames = list_css_renames(repo, base_ref, target_ref)
    if not renames:
        return []
    base_refs = collect_template_css_refs(repo, base_ref)
    target_refs = collect_template_css_refs(repo, target_ref)
    target_by_scope_key: dict[tuple[str, str], set[str]] = {}
    for tpl in target_refs:
        key = template_scope_key(tpl)
        if key is None:
            continue
        target_by_scope_key.setdefault(key, set()).add(tpl)
    merged: dict[tuple[str, str], RenameAuditBucket] = {}
    for old_path, new_path in renames:
        old_ref = css_path_to_template_ref(old_path)
        new_ref = css_path_to_template_ref(new_path)
        if not old_ref or not new_ref:
            continue
        base_users = {tpl for tpl, refs in base_refs.items() if old_ref in refs}
        unresolved: set[str] = set()
        migrated: set[str] = set()
        dropped: set[str] = set()

        for base_tpl in base_users:
            candidates: set[str] = set()
            if base_tpl in target_refs:
                candidates.add(base_tpl)
            key = template_scope_key(base_tpl)
            if key is not None:
                candidates.update(target_by_scope_key.get(key, set()))

            if not candidates:
                dropped.add(base_tpl)
                continue

            if any(old_ref in target_refs.get(candidate, set()) for candidate in candidates):
                unresolved.add(base_tpl)
            elif any(new_ref in target_refs.get(candidate, set()) for candidate in candidates):
                migrated.add(base_tpl)
            else:
                dropped.add(base_tpl)

        unresolved_sorted = sorted(unresolved)
        migrated_sorted = sorted(migrated)
        dropped_sorted = sorted(dropped)
        key = (old_ref, new_ref)
        if key not in merged:
            merged[key] = RenameAuditBucket(
                unresolved=set(),
                migrated=set(),
                dropped=set(),
                rename_pairs=set(),
            )
        merged[key].unresolved.update(unresolved_sorted)
        merged[key].migrated.update(migrated_sorted)
        merged[key].dropped.update(dropped_sorted)
        merged[key].rename_pairs.add((old_path, new_path))

    audits: list[CssRenameAudit] = []
    for (old_ref, new_ref), buckets in sorted(merged.items()):
        audits.append(
            CssRenameAudit(
                old_template_ref=old_ref,
                new_template_ref=new_ref,
                rename_path_pairs=tuple(sorted(buckets.rename_pairs)),
                unresolved_templates=tuple(sorted(buckets.unresolved)),
                migrated_templates=tuple(sorted(buckets.migrated)),
                dropped_templates=tuple(sorted(buckets.dropped)),
            )
        )
    return audits


def summarize_template_scope(paths: Iterable[str]) -> str:
    counts: dict[str, int] = {}
    for path in paths:
        parts = PurePosixPath(path).parts
        scope = parts[1] if len(parts) > 1 and parts[0] == "templates" else "unknown"
        counts[scope] = counts.get(scope, 0) + 1
    if not counts:
        return "-"
    ordered = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    return ", ".join(f"{scope}={count}" for scope, count in ordered)


def suppress_modularized_added(
    added: list[str],
    base: dict[str, ComponentContract],
    target: dict[str, ComponentContract],
    base_all_flattened: list[str] | None = None,
) -> tuple[list[str], list[str]]:
    """
    Suppress added templates that look like extracted fragments:
    if flattened normalized target content is fully contained in any
    flattened normalized base template, treat it as modularization noise.
    """
    base_flattened = {
        contract.flattened_normalized
        for contract in base.values()
        if contract.flattened_normalized
    }
    if base_all_flattened:
        base_flattened.update(base_all_flattened)
    kept: list[str] = []
    suppressed: list[str] = []
    for path in added:
        added_flat = target[path].flattened_normalized
        if not added_flat:
            kept.append(path)
            continue
        if added_flat in base_flattened:
            suppressed.append(path)
        else:
            kept.append(path)
    return kept, suppressed


def suppress_modularized_removed(
    removed: list[str],
    base: dict[str, ComponentContract],
    target: dict[str, ComponentContract],
    target_all_flattened: list[str] | None = None,
) -> tuple[list[str], list[str]]:
    """
    Suppress removed templates that look like moved/extracted content:
    if flattened normalized base content is fully contained in any
    flattened normalized target template, treat it as modularization noise.
    """
    target_flattened = {
        contract.flattened_normalized
        for contract in target.values()
        if contract.flattened_normalized
    }
    if target_all_flattened:
        target_flattened.update(target_all_flattened)
    kept: list[str] = []
    suppressed: list[str] = []
    for path in removed:
        base_flat = base[path].flattened_normalized
        if not base_flat:
            kept.append(path)
            continue
        if base_flat in target_flattened:
            suppressed.append(path)
        else:
            kept.append(path)
    return kept, suppressed


def collect_all_html_normalized(repo: str, ref: str) -> list[str]:
    normalized: list[str] = []
    for path in list_files(repo, ref, ""):
        if not path.endswith(".html"):
            continue
        content = read_file(repo, ref, path)
        if not content:
            continue
        normalized.append(normalize_template_text(content))
    return normalized


def extract_moved_templates(
    repo: str,
    base_ref: str,
    target_ref: str,
    removed: list[str],
    added: list[str],
    base_contracts: dict[str, ComponentContract],
    target_contracts: dict[str, ComponentContract],
) -> tuple[list[tuple[str, str]], list[str], list[str]]:
    rename_pairs = list_template_renames(repo, base_ref, target_ref)
    removed_set = set(removed)
    added_set = set(added)
    moved: list[tuple[str, str]] = []
    for old_path, new_path in rename_pairs:
        if old_path in removed_set and new_path in added_set:
            moved.append((old_path, new_path))
            removed_set.remove(old_path)
            added_set.remove(new_path)

    # Heuristic fallback for WORKTREE/complex refactors where git rename
    # detection misses logical moves.
    added_by_key: dict[tuple[str, str], list[str]] = {}
    for path in sorted(added_set):
        key = template_scope_key(path)
        if key is None:
            continue
        added_by_key.setdefault(key, []).append(path)

    target_norm_by_path = {
        path: contract.flattened_normalized
        for path, contract in target_contracts.items()
        if contract.flattened_normalized
    }
    base_norm_by_path = {
        path: contract.flattened_normalized
        for path, contract in base_contracts.items()
        if contract.flattened_normalized
    }

    for old_path in sorted(list(removed_set)):
        key = template_scope_key(old_path)
        if key is None:
            continue
        candidates = added_by_key.get(key, [])
        if not candidates:
            continue

        old_norm = base_norm_by_path.get(old_path)
        if not old_norm:
            continue

        best_candidate = None
        best_score = 0.0
        for candidate in candidates:
            new_norm = target_norm_by_path.get(candidate)
            if not new_norm:
                continue
            # Cheap pre-filter to avoid expensive sequence comparisons.
            length_ratio = min(len(old_norm), len(new_norm)) / max(len(old_norm), len(new_norm))
            if length_ratio < 0.80:
                continue
            score = difflib.SequenceMatcher(None, old_norm, new_norm).ratio()
            if score > best_score:
                best_score = score
                best_candidate = candidate

        if best_candidate and best_score >= 0.92:
            moved.append((old_path, best_candidate))
            removed_set.remove(old_path)
            added_set.remove(best_candidate)
            added_by_key[key].remove(best_candidate)

    return sorted(moved), sorted(removed_set), sorted(added_set)


def print_changed_details(
    changed: list[str],
    base: dict[str, ComponentContract],
    target: dict[str, ComponentContract],
    show_flatten_diff: bool = False,
    flatten_diff_lines: int = 200,
    use_color: bool = False,
) -> None:
    for template in changed:
        print(
            f"\n{style('CHANGED', Colors.BOLD, Colors.YELLOW, use_color=use_color)}: "
            f"{template}"
        )
        base_css = set(base[template].css_fingerprints)
        target_css = set(target[template].css_fingerprints)

        removed_css = sorted(base_css - target_css)
        added_css = sorted(target_css - base_css)

        if removed_css:
            print(f"  {style('removed css content fingerprints:', Colors.RED, use_color=use_color)}")
            for item in removed_css:
                print(f"    {style('-', Colors.RED, use_color=use_color)} {item}")
        if added_css:
            print(f"  {style('added css content fingerprints:', Colors.GREEN, use_color=use_color)}")
            for item in added_css:
                print(f"    {style('+', Colors.GREEN, use_color=use_color)} {item}")

        if not removed_css and not added_css:
            print(f"  {style('same css files but normalized content changed', Colors.CYAN, use_color=use_color)}")
        if (
            show_flatten_diff
            and base[template].flattened_pretty is not None
            and target[template].flattened_pretty is not None
            and base[template].template_fingerprint != target[template].template_fingerprint
        ):
            before = base[template].flattened_pretty.splitlines()
            after = target[template].flattened_pretty.splitlines()
            diff_lines = list(
                difflib.unified_diff(
                    before,
                    after,
                    fromfile=f"{template} (base)",
                    tofile=f"{template} (target)",
                    lineterm="",
                )
            )
            if diff_lines:
                print(f"  {style('flattened diff (normalized):', Colors.BOLD, use_color=use_color)}")
                for line in diff_lines[:flatten_diff_lines]:
                    line_color = ()
                    if line.startswith("---") or line.startswith("+++") or line.startswith("@@"):
                        line_color = (Colors.CYAN,)
                    elif line.startswith("+"):
                        line_color = (Colors.GREEN,)
                    elif line.startswith("-"):
                        line_color = (Colors.RED,)
                    print(f"    {style(line, *line_color, use_color=use_color)}")
                if len(diff_lines) > flatten_diff_lines:
                    remaining = len(diff_lines) - flatten_diff_lines
                    print(
                        "    "
                        + style(
                            f"... diff truncated ({remaining} more lines)",
                            Colors.DIM,
                            use_color=use_color,
                        )
                    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Diff frontend CSS contracts between git refs."
    )
    parser.add_argument(
        "--base-ref",
        default="develop",
        help="Base git ref to compare against (default: develop)",
    )
    parser.add_argument(
        "--target-ref",
        default="WORKTREE",
        help=(
            "Target git ref, or WORKTREE to include unstaged changes "
            "(default: WORKTREE)"
        ),
    )
    parser.add_argument(
        "--association",
        action="append",
        dest="associations",
        help=(
            "Association/theme to include. Can be repeated. "
            "Defaults to date, kk, on, demo, biocum."
        ),
    )
    parser.add_argument(
        "--template-glob",
        action="append",
        dest="template_globs",
        help=(
            "Glob pattern for component templates. Use {association} placeholder. "
            "Can be repeated."
        ),
    )
    parser.add_argument(
        "--exclude-template-glob",
        action="append",
        dest="exclude_template_globs",
        help="Glob pattern to exclude templates. Can be repeated.",
    )
    parser.add_argument(
        "--include-emails",
        action="store_true",
        help="Include email templates in comparison.",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Return non-zero exit code when any difference is found.",
    )
    parser.add_argument(
        "--declaration-only",
        dest="declaration_only",
        action="store_true",
        default=True,
        help=(
            "Ignore selector names and compare only normalized declaration blocks "
            "(default: on)."
        ),
    )
    parser.add_argument(
        "--full-css",
        dest="declaration_only",
        action="store_false",
        help="Disable declaration-only mode and compare full CSS (selectors included).",
    )
    parser.add_argument(
        "--flatten-templates",
        dest="flatten_templates",
        action="store_true",
        default=True,
        help=(
            "Recursively inline {%% include %%} and compare normalized flattened "
            "template content in addition to CSS contracts (default: on)."
        ),
    )
    parser.add_argument(
        "--no-flatten-templates",
        dest="flatten_templates",
        action="store_false",
        help="Disable flattened template comparison.",
    )
    parser.add_argument(
        "--common-only",
        dest="common_only",
        action="store_true",
        default=False,
        help="Only compare templates that exist in both refs (default: off).",
    )
    parser.add_argument(
        "--include-added-removed",
        dest="common_only",
        action="store_false",
        help="Also report added/removed template paths between refs (default behavior).",
    )
    parser.add_argument(
        "--show-flatten-diff",
        action="store_true",
        help=(
            "For changed templates, print unified diff of normalized flattened "
            "template content (when flattening is enabled)."
        ),
    )
    parser.add_argument(
        "--flatten-diff-lines",
        type=int,
        default=200,
        help="Max flattened diff lines printed per changed template (default: 200).",
    )
    parser.add_argument(
        "--flatten-diff-wrap",
        type=int,
        default=100,
        help="Wrap width for flattened template diff formatting (default: 100).",
    )
    parser.add_argument(
        "--no-color",
        action="store_true",
        help="Disable ANSI colors in output.",
    )
    parser.add_argument(
        "--no-css-rename-audit",
        action="store_true",
        help="Disable audit for template refs when CSS files are renamed between refs.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print machine-readable JSON output.",
    )

    args = parser.parse_args()
    repo = "."
    associations = tuple(args.associations or DEFAULT_ASSOCIATIONS)
    template_globs = tuple(args.template_globs or DEFAULT_TEMPLATE_GLOBS)
    if args.exclude_template_globs:
        exclude_template_globs = tuple(args.exclude_template_globs)
    else:
        exclude_template_globs = () if args.include_emails else DEFAULT_EXCLUDE_TEMPLATE_GLOBS

    try:
        css_ref_canonical_map = build_css_ref_canonical_map(
            repo, args.base_ref, args.target_ref
        )
        base_contracts = collect_contracts(
            repo=repo,
            ref=args.base_ref,
            associations=associations,
            template_globs=template_globs,
            exclude_template_globs=exclude_template_globs,
            declaration_only=args.declaration_only,
            flatten_templates=args.flatten_templates,
            diff_wrap_width=args.flatten_diff_wrap,
            css_ref_canonical_map=css_ref_canonical_map,
        )
        target_contracts = collect_contracts(
            repo=repo,
            ref=args.target_ref,
            associations=associations,
            template_globs=template_globs,
            exclude_template_globs=exclude_template_globs,
            declaration_only=args.declaration_only,
            flatten_templates=args.flatten_templates,
            diff_wrap_width=args.flatten_diff_wrap,
            css_ref_canonical_map=css_ref_canonical_map,
        )
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    removed, added, changed = diff_contracts(
        base_contracts, target_contracts, common_only=args.common_only
    )
    rename_audits: list[CssRenameAudit] = []
    if not args.no_css_rename_audit:
        rename_audits = audit_css_rename_refs(repo, args.base_ref, args.target_ref)
    suppressed_added: list[str] = []
    suppressed_removed: list[str] = []
    if args.flatten_templates and added:
        base_all_flattened = collect_all_html_normalized(repo, args.base_ref)
        added, suppressed_added = suppress_modularized_added(
            added,
            base_contracts,
            target_contracts,
            base_all_flattened=base_all_flattened,
        )
    if args.flatten_templates and removed:
        target_all_flattened = collect_all_html_normalized(repo, args.target_ref)
        removed, suppressed_removed = suppress_modularized_removed(
            removed,
            base_contracts,
            target_contracts,
            target_all_flattened=target_all_flattened,
        )
    moved_templates: list[tuple[str, str]] = []
    if removed and added:
        moved_templates, removed, added = extract_moved_templates(
            repo,
            args.base_ref,
            args.target_ref,
            removed,
            added,
            base_contracts,
            target_contracts,
        )
    total_base = len(base_contracts)
    total_target = len(target_contracts)

    use_color = sys.stdout.isatty() and not args.no_color
    has_unresolved_rename_refs = any(a.unresolved_templates for a in rename_audits)

    if args.json:
        payload = {
            "base_ref": args.base_ref,
            "target_ref": args.target_ref,
            "mode": "declaration-only" if args.declaration_only else "full-css",
            "flatten_templates": args.flatten_templates,
            "associations": list(associations),
            "templates_scanned": {"base": total_base, "target": total_target},
            "summary": {
                "removed": len(removed),
                "added": len(added),
                "changed": len(changed),
                "moved": len(moved_templates),
                "suppressed_added_modularized": len(suppressed_added),
                "suppressed_removed_modularized": len(suppressed_removed),
                "has_unresolved_css_rename_refs": has_unresolved_rename_refs,
            },
            "removed_templates": removed,
            "added_templates": added,
            "moved_templates": [
                {"from": old_path, "to": new_path} for old_path, new_path in moved_templates
            ],
            "changed_templates": changed,
            "css_rename_audit": [
                {
                    "old_ref": audit.old_template_ref,
                    "new_ref": audit.new_template_ref,
                    "scope": summarize_template_scope(
                        set(audit.migrated_templates)
                        | set(audit.unresolved_templates)
                        | set(audit.dropped_templates)
                    ),
                    "path_pairs": [
                        {"from": old_path, "to": new_path}
                        for old_path, new_path in audit.rename_path_pairs
                    ],
                    "migrated_templates": list(audit.migrated_templates),
                    "unresolved_templates": list(audit.unresolved_templates),
                    "dropped_templates": list(audit.dropped_templates),
                }
                for audit in rename_audits
            ],
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        if args.strict and (removed or added or changed or has_unresolved_rename_refs):
            return 1
        return 0

    print(f"{style('Base ref', Colors.BOLD, use_color=use_color)}:   {args.base_ref}")
    print(f"{style('Target ref', Colors.BOLD, use_color=use_color)}: {args.target_ref}")
    print(
        f"{style('Mode', Colors.BOLD, use_color=use_color)}: "
        f"{'declaration-only' if args.declaration_only else 'full-css'}"
    )
    print(
        f"{style('Flatten templates', Colors.BOLD, use_color=use_color)}: "
        f"{'on' if args.flatten_templates else 'off'}"
    )
    print(f"{style('Associations', Colors.BOLD, use_color=use_color)}: {', '.join(associations)}")
    print(
        f"{style('Templates scanned', Colors.BOLD, use_color=use_color)}: "
        f"base={total_base}, target={total_target}"
    )
    print(
        f"{style('Diff summary', Colors.BOLD, use_color=use_color)}: "
        f"removed={style(str(len(removed)), Colors.RED if removed else Colors.DIM, use_color=use_color)}, "
        f"added={style(str(len(added)), Colors.GREEN if added else Colors.DIM, use_color=use_color)}, "
        f"changed={style(str(len(changed)), Colors.YELLOW if changed else Colors.DIM, use_color=use_color)}"
    )
    if suppressed_added:
        print(
            f"{style('Suppressed added (modularized)', Colors.BOLD, use_color=use_color)}: "
            f"{style(str(len(suppressed_added)), Colors.DIM, use_color=use_color)}"
        )
    if suppressed_removed:
        print(
            f"{style('Suppressed removed (modularized)', Colors.BOLD, use_color=use_color)}: "
            f"{style(str(len(suppressed_removed)), Colors.DIM, use_color=use_color)}"
        )
    if moved_templates:
        print(
            f"{style('Detected moves', Colors.BOLD, use_color=use_color)}: "
            f"{style(str(len(moved_templates)), Colors.DIM, use_color=use_color)}"
        )

    if removed:
        print(f"\n{style('REMOVED templates:', Colors.BOLD, Colors.RED, use_color=use_color)}")
        for path in removed:
            print(f"  {style('-', Colors.RED, use_color=use_color)} {path}")

    if added:
        print(f"\n{style('ADDED templates:', Colors.BOLD, Colors.GREEN, use_color=use_color)}")
        for path in added:
            print(f"  {style('+', Colors.GREEN, use_color=use_color)} {path}")
    if moved_templates:
        print(f"\n{style('MOVED templates:', Colors.BOLD, Colors.CYAN, use_color=use_color)}")
        for old_path, new_path in moved_templates:
            print(
                f"  {style('~', Colors.CYAN, use_color=use_color)} "
                f"{old_path} -> {new_path}"
            )

    if changed:
        print_changed_details(
            changed,
            base_contracts,
            target_contracts,
            show_flatten_diff=args.show_flatten_diff,
            flatten_diff_lines=args.flatten_diff_lines,
            use_color=use_color,
        )
    else:
        print(
            "\n"
            + style(
                "No CSS contract differences detected.",
                Colors.GREEN,
                use_color=use_color,
            )
        )

    if rename_audits:
        print(f"\n{style('CSS rename audit:', Colors.BOLD, use_color=use_color)}")
        unresolved_total = 0
        for audit in rename_audits:
            unresolved_count = len(audit.unresolved_templates)
            unresolved_total += unresolved_count
            status_color = Colors.GREEN if unresolved_count == 0 else Colors.RED
            scope_paths = (
                set(audit.migrated_templates)
                | set(audit.unresolved_templates)
                | set(audit.dropped_templates)
            )
            scope_summary = summarize_template_scope(scope_paths)
            print(
                "  "
                + style(
                    f"{audit.old_template_ref} -> {audit.new_template_ref}",
                    status_color,
                    use_color=use_color,
                )
                + (
                    f" (scope: {scope_summary}; migrated={len(audit.migrated_templates)}, "
                    f"unresolved={unresolved_count}, dropped={len(audit.dropped_templates)})"
                )
            )
            preview_pairs = list(audit.rename_path_pairs[:3])
            for old_path, new_path in preview_pairs:
                print(
                    "    "
                    + style("path", Colors.DIM, use_color=use_color)
                    + f": {old_path} -> {new_path}"
                )
            if len(audit.rename_path_pairs) > 3:
                print(
                    "    "
                    + style(
                        f"... {len(audit.rename_path_pairs) - 3} more path rename(s)",
                        Colors.DIM,
                        use_color=use_color,
                    )
                )
            if unresolved_count:
                for tpl in audit.unresolved_templates[:10]:
                    print(f"    {style('-', Colors.RED, use_color=use_color)} {tpl} still references old path")
                if unresolved_count > 10:
                    print(
                        "    "
                        + style(
                            f"... {unresolved_count - 10} more unresolved templates",
                            Colors.DIM,
                            use_color=use_color,
                        )
                    )
        if unresolved_total == 0:
            print("  " + style("No lingering old CSS references detected.", Colors.GREEN, use_color=use_color))

    if args.strict and (removed or added or changed or has_unresolved_rename_refs):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
