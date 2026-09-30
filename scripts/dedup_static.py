"""Deduplicate identical files across the per-variant collected static trees.

Every variant's collectstatic output contains the full shared asset set plus
its own overrides, so the seven trees are nearly identical. Replacing
identical files with hardlinks collapses them to a single inode on disk,
which keeps the generic image lean without changing any served content.

The trees are treated as immutable build output: files are never modified in
place, only re-linked to an existing identical sibling.
"""

from __future__ import annotations

import hashlib
import os
import sys
from collections.abc import Iterator


def iter_files(root: str) -> Iterator[str]:
    for dirpath, _dirnames, filenames in os.walk(root):
        for name in sorted(filenames):
            yield os.path.join(dirpath, name)


def sha256_file(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def deduplicate(root: str) -> tuple[int, int]:
    """Hardlink identical files across trees; returns (linked, bytes_saved)."""
    by_key: dict[tuple[int, str], str] = {}
    linked = 0
    saved = 0
    for path in iter_files(root):
        if os.path.islink(path):
            continue
        size = os.path.getsize(path)
        if size == 0:
            continue
        key = (size, sha256_file(path))
        first = by_key.get(key)
        if first is None:
            by_key[key] = path
            continue
        if os.path.samefile(path, first):
            continue
        os.remove(path)
        os.link(first, path)
        linked += 1
        saved += size
    return linked, saved


def main() -> int:
    if len(sys.argv) != 2:
        print(f"usage: {sys.argv[0]} <static-collected-root>", file=sys.stderr)
        return 2
    root = sys.argv[1]
    if not os.path.isdir(root):
        print(f"{root} is not a directory", file=sys.stderr)
        return 2
    linked, saved = deduplicate(root)
    print(f"dedup_static: hardlinked {linked} files, saved {saved / (1024 * 1024):.1f} MiB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
