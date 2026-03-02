import os
import subprocess
from pathlib import PurePosixPath


def run_git(repo: str, args: list[str]) -> str:
    proc = subprocess.run(
        ["git", *args],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed:\n{proc.stderr.strip()}")
    return proc.stdout


def list_files(repo: str, ref: str, prefix: str) -> list[str]:
    if ref.upper() == "WORKTREE":
        root = PurePosixPath(prefix or ".")
        results: list[str] = []
        for dirpath, _, filenames in os.walk(repo):
            for filename in filenames:
                rel_str = os.path.relpath(os.path.join(dirpath, filename), repo).replace("\\", "/")
                rel = PurePosixPath(rel_str)
                rel_str = rel.as_posix()
                if root == PurePosixPath(".") or rel.is_relative_to(root):
                    results.append(rel_str)
        return sorted(results)

    pathspec = prefix or "."
    out = run_git(repo, ["ls-tree", "-r", "--name-only", ref, "--", pathspec])
    return [line.strip() for line in out.splitlines() if line.strip()]


def read_file(repo: str, ref: str, path: str) -> str | None:
    if ref.upper() == "WORKTREE":
        full_path = os.path.join(repo, path)
        if not os.path.exists(full_path):
            return None
        with open(full_path, "r", encoding="utf-8", errors="replace") as file:
            return file.read()

    proc = subprocess.run(
        ["git", "show", f"{ref}:{path}"],
        cwd=repo,
        capture_output=True,
        text=False,
        check=False,
    )
    if proc.returncode != 0:
        return None
    return proc.stdout.decode("utf-8", errors="replace")


def list_css_renames(repo: str, base_ref: str, target_ref: str) -> list[tuple[str, str]]:
    if target_ref.upper() == "WORKTREE":
        out = run_git(repo, ["diff", "--name-status", base_ref, "--", "static"])
    else:
        out = run_git(repo, ["diff", "--name-status", f"{base_ref}..{target_ref}", "--", "static"])
    renames: list[tuple[str, str]] = []
    for line in out.splitlines():
        cols = line.strip().split("\t")
        if len(cols) != 3:
            continue
        status, old_path, new_path = cols
        if not status.startswith("R"):
            continue
        if not old_path.endswith(".css") or not new_path.endswith(".css"):
            continue
        renames.append((old_path, new_path))
    return renames


def list_template_renames(repo: str, base_ref: str, target_ref: str) -> list[tuple[str, str]]:
    if target_ref.upper() == "WORKTREE":
        out = run_git(repo, ["diff", "--name-status", base_ref, "--", "templates"])
    else:
        out = run_git(repo, ["diff", "--name-status", f"{base_ref}..{target_ref}", "--", "templates"])
    renames: list[tuple[str, str]] = []
    for line in out.splitlines():
        cols = line.strip().split("\t")
        if len(cols) != 3:
            continue
        status, old_path, new_path = cols
        if not status.startswith("R"):
            continue
        if not old_path.endswith(".html") or not new_path.endswith(".html"):
            continue
        renames.append((old_path, new_path))
    return renames
