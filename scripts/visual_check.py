#!/usr/bin/env python
"""Render and screenshot pages from a checkout, for cross-version visual checks.

Why this exists: dependency bumps that touch the admin theme (Django itself,
django-unfold) can regress layout without failing a single test. A test can
assert 200 on a changelist while the page behind it is visibly broken. This
script renders pages through the real settings, templates and static files,
screenshots them with headless Chromium, and can pixel-diff two runs.

It must run inside the checkout whose versions you want to render, because the
installed dependencies are what is under test. Comparing two versions therefore
means running it once per checkout (two git worktrees work well):

    cd /path/to/checkout-main && python scripts/visual_check.py capture --out /tmp/base
    cd /path/to/checkout-branch && python scripts/visual_check.py capture --out /tmp/cand --unfold
    python scripts/visual_check.py compare --base /tmp/base --candidate /tmp/cand

The capture step uses core.settings.test (in-memory SQLite, no services), creates
a superuser, signs it in with the test client, and collects static files into the
output directory so the screenshots carry real CSS and fonts. Nothing is written
inside the checkout.

Chromium is found on PATH or in the Playwright browser cache. Override with
--chrome or CHROME_PATH.
"""

from __future__ import annotations

import argparse
import functools
import glob
import json
import os
import shutil
import subprocess
import sys
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

DEFAULT_MODELS = (
    "members.Member",
    "members.Subscription",
    "news.Post",
    "events.Event",
    "ctf.Ctf",
    "staticpages.StaticPage",
    "publications.PDFFile",
    "archive.DocumentCollection",
)

DEFAULT_URLS = {
    "admin-index": "/admin/",
    "archive-documents": "/archive/documents/",
}

WIDTH = 1600
HEIGHTS = (1000, 2600)
VIRTUAL_TIME_BUDGET_MS = 3000
CHROME_GLOBS = (
    "~/.cache/ms-playwright/chromium-*/chrome-linux64/chrome",
    "~/.cache/ms-playwright/chromium-*/chrome-linux/chrome",
    "~/.cache/ms-playwright/chromium_headless_shell-*/chrome-headless-shell-linux64/chrome-headless-shell",
)
CHROME_NAMES = ("chromium", "chromium-browser", "google-chrome", "google-chrome-stable")


def find_chrome(explicit: str | None) -> str:
    if explicit:
        return explicit
    env = os.environ.get("CHROME_PATH")
    if env and Path(env).exists():
        return env
    for name in CHROME_NAMES:
        found = shutil.which(name)
        if found:
            return found
    for pattern in CHROME_GLOBS:
        matches = sorted(glob.glob(os.path.expanduser(pattern)))
        if matches:
            return matches[-1]
    raise SystemExit("No Chromium found. Install one, set CHROME_PATH, or pass --chrome /path/to/chrome.")


# --------------------------------------------------------------------------
# capture
# --------------------------------------------------------------------------


def boot_django(project_dir: Path, *, unfold: bool, project_name: str) -> None:
    """Import the project under test. Must run before any django import."""
    sys.path.insert(0, str(project_dir))
    os.environ["DJANGO_SETTINGS_MODULE"] = "core.settings.test"
    os.environ["TEST"] = "1"
    os.environ["PROJECT_NAME"] = project_name
    if unfold:
        os.environ["USE_UNFOLD"] = "True"
    else:
        os.environ.pop("USE_UNFOLD", None)


def resolve_pages(models: list[str], extra_urls: dict[str, str]) -> list[tuple[str, str]]:
    from django.contrib import admin
    from django.urls import NoReverseMatch, reverse

    registry = {(m._meta.app_label, m._meta.model_name): m for m in admin.site._registry}
    pages: list[tuple[str, str]] = [(label, path) for label, path in DEFAULT_URLS.items()]
    for spec in models:
        app_label, _, model_name = spec.partition(".")
        app_label, model_name = app_label.lower(), model_name.lower()
        if (app_label, model_name) not in registry:
            print(f"  note: {spec} is not registered in the admin, skipping")
            continue
        slug = f"{app_label}-{model_name}"
        for suffix, view in (("changelist", "changelist"), ("add", "add")):
            url_name = f"admin:{app_label}_{model_name}_{view}"
            try:
                path = reverse(url_name)
            except NoReverseMatch:
                print(f"  note: {url_name} does not reverse, skipping")
                continue
            pages.append((f"{slug}-{suffix}", path))
    pages.extend((label, path) for label, path in extra_urls.items())

    seen: set[str] = set()
    unique: list[tuple[str, str]] = []
    for label, path in pages:
        if label in seen:
            continue
        seen.add(label)
        unique.append((label, path))
    return unique


def signed_in_client():  # noqa: ANN201
    """A test Client with a superuser signed in, ready to replay requests."""
    from django.contrib.auth import get_user_model
    from django.test import Client

    user = get_user_model().objects.create_superuser(
        username="visual-check", password="visual-check", email="visual-check@example.com"
    )
    client = Client()
    client.force_login(user)
    return client


def probe_pages(pages: list[tuple[str, str]], client) -> dict[str, dict[str, str | int]]:  # noqa: ANN001
    """Check every page before screenshotting, so a 403 or 500 is visible."""
    results: dict[str, dict[str, str | int]] = {}
    for label, path in pages:
        response = client.get(path)
        entry: dict[str, str | int] = {"path": path, "status": response.status_code}
        if response.status_code in (301, 302):
            entry["location"] = response.headers.get("Location", "")
        results[label] = entry
        detail = f"{response.status_code}"
        if entry.get("location"):
            detail += f" -> {entry['location']}"
        print(f"  {label:34} {detail}")
    return results


def collect_static(out: Path) -> int:
    """Collect static into out/static.

    The caller must hold override_settings(STATIC_ROOT=...) while this runs.
    Assigning settings.STATIC_ROOT directly is not enough: the staticfiles
    storage caches its location when it is first used, and rendering a page
    first binds it to the checkout's own static directory, which makes
    collectstatic write into the source tree instead of the output directory.
    """
    from django.core.management import call_command

    static_root = out / "static"
    call_command("collectstatic", interactive=False, verbosity=0)
    return sum(1 for path in static_root.rglob("*") if path.is_file())


class _ReplayHandler(SimpleHTTPRequestHandler):
    """Serve collected static from disk, and everything else from Django.

    Replaying requests through the Django test client instead of saving HTML to
    files keeps the response headers, which matters: Django sends the charset in
    Content-Type rather than in a meta tag, so a saved-then-served page renders
    its Swedish text as mojibake. It also lets Chrome fetch real endpoints such
    as /admin/jsi18n/.
    """

    django_client = None  # set before the server starts
    _lock = threading.Lock()

    def log_message(self, *args: object) -> None:  # noqa: D102
        pass

    def do_GET(self) -> None:  # noqa: N802
        path = self.path.split("?", 1)[0]
        if path.startswith("/static/") or path == "/media":
            super().do_GET()
            return
        with self._lock:
            response = self.django_client.get(self.path)
        body = response.content
        self.send_response(response.status_code)
        for header, value in response.headers.items():
            if header.lower() in {"content-length", "transfer-encoding", "connection"}:
                continue
            self.send_header(header, value)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def start_server(directory: Path, client) -> tuple[ThreadingHTTPServer, int]:  # noqa: ANN001
    handler = functools.partial(_ReplayHandler, directory=str(directory))
    _ReplayHandler.django_client = client
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    return httpd, httpd.server_address[1]


def screenshot(chrome: str, url: str, png: Path, *, width: int, height: int) -> bool:
    # No --user-data-dir here on purpose: the Chromium build available on this
    # machine hangs for minutes when one is passed (reproduced with a fresh and
    # a pre-created profile, on tmpfs and on the home filesystem) and completes
    # in about a second without it.
    cmd = [
        chrome,
        "--headless=new",
        "--no-sandbox",
        "--disable-gpu",
        "--disable-dev-shm-usage",
        "--disable-extensions",
        "--no-first-run",
        "--no-default-browser-check",
        "--hide-scrollbars",
        "--force-device-scale-factor=1",
        f"--virtual-time-budget={VIRTUAL_TIME_BUDGET_MS}",
        f"--window-size={width},{height}",
        f"--screenshot={png}",
        url,
    ]
    try:
        subprocess.run(cmd, check=False, timeout=180, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except subprocess.TimeoutExpired:
        return False
    return png.exists() and png.stat().st_size > 0


def cmd_capture(args: argparse.Namespace) -> int:
    project_dir = Path(args.project_dir or os.getcwd()).resolve()
    out = Path(args.out).resolve()
    if out.exists() and args.clean:
        shutil.rmtree(out)
    out.mkdir(parents=True, exist_ok=True)

    boot_django(project_dir, unfold=args.unfold, project_name=args.project_name)

    import django

    django.setup()
    import importlib.metadata as md

    from django.conf import settings
    from django.test import override_settings
    from django.test.runner import DiscoverRunner
    from django.test.utils import setup_test_environment, teardown_test_environment

    chrome = None if args.no_screenshot else find_chrome(args.chrome)
    heights = [int(h) for h in args.heights.split(",")]
    pages = resolve_pages(args.model, dict(u.split("=", 1) for u in args.url))

    # override_settings (not a bare assignment) so the staticfiles storage is
    # rebound to the output directory and the checkout's static tree is never
    # touched, however the body below is reordered later.
    with override_settings(STATIC_ROOT=str(out / "static")):
        static_root = Path(settings.STATIC_ROOT).resolve()
        if not static_root.is_relative_to(out):
            raise SystemExit(f"refusing to collect static: {static_root} is outside {out}")

        setup_test_environment()
        runner = DiscoverRunner(verbosity=0, interactive=False)
        old_config = runner.setup_databases()
        try:
            print(
                f"### capture  project={project_dir}\n"
                f"    django={md.version('django')} django-unfold={md.version('django-unfold')} "
                f"USE_UNFOLD={settings.USE_UNFOLD} chrome={chrome or 'skipped'}"
            )
            print("### collecting static")
            files = collect_static(out)
            print(f"  {files} static files into {static_root}")

            client = signed_in_client()
            print(f"### probing {len(pages)} pages")
            results = probe_pages(pages, client)

            manifest: dict[str, object] = {
                "project_dir": str(project_dir),
                "django": md.version("django"),
                "django_unfold": md.version("django-unfold"),
                "use_unfold": bool(settings.USE_UNFOLD),
                "width": args.width,
                "heights": heights,
                "pages": results,
                "shots": {},
            }

            if chrome:
                httpd, port = start_server(out, client)
                base_url = f"http://127.0.0.1:{port}"
                print(f"### screenshotting at {base_url} ({args.width}x{heights})")
                try:
                    for label, entry in results.items():
                        shots = []
                        for height in heights:
                            png = out / f"{label}.{height}.png"
                            ok = screenshot(
                                chrome,
                                f"{base_url}{entry['path']}",
                                png,
                                width=args.width,
                                height=height,
                            )
                            print(f"  {label:34} {height}px  {'ok' if ok else 'FAILED'}")
                            if ok:
                                shots.append(png.name)
                        manifest["shots"][label] = shots  # type: ignore[index]
                finally:
                    httpd.shutdown()
                    httpd.server_close()

            (out / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
            print(f"### wrote {out / 'manifest.json'}")
        finally:
            runner.teardown_databases(old_config)
            teardown_test_environment()
    return 0


# --------------------------------------------------------------------------
# compare
# --------------------------------------------------------------------------


def cmd_compare(args: argparse.Namespace) -> int:
    from PIL import Image, ImageChops, ImageStat

    base = Path(args.base).resolve()
    candidate = Path(args.candidate).resolve()
    out = Path(args.out).resolve() if args.out else None
    if out:
        out.mkdir(parents=True, exist_ok=True)

    rows: list[tuple[float, str, str]] = []
    for png in sorted(base.glob("*.png")):
        other = candidate / png.name
        if not other.exists():
            rows.append((float("nan"), png.name, "missing in candidate"))
            continue
        with Image.open(png) as handle:
            left = handle.convert("RGB")
        with Image.open(other) as handle:
            right = handle.convert("RGB")
        if left.size != right.size:
            rows.append((float("nan"), png.name, f"size differs {left.size} vs {right.size}"))
            continue
        difference = ImageChops.difference(left, right)
        mask = difference.convert("L").point(lambda value: 255 if value > args.threshold else 0)
        changed = int(ImageStat.Stat(mask).sum[0] // 255)
        percent = 100.0 * changed / (left.width * left.height)
        bbox = mask.getbbox()
        note = "identical" if bbox is None else f"bbox={bbox}"
        rows.append((percent, png.name, note))

        if out is not None and (bbox is not None or args.all_composites):
            sheet = Image.new("RGB", (left.width * 2 + 8, left.height), (220, 0, 0))
            sheet.paste(left, (0, 0))
            sheet.paste(right, (left.width + 8, 0))
            sheet.save(out / f"{png.stem}.side.png")
            if bbox is not None:
                difference.save(out / f"{png.stem}.diff.png")

    rows.sort(key=lambda row: (row[0] != row[0], -row[0]))
    print(f"base={base}\ncandidate={candidate}\n")
    print(f"{'changed %':>10}  {'page':44} note")
    for percent, name, note in rows:
        shown = "n/a" if percent != percent else f"{percent:.3f}"
        print(f"{shown:>10}  {name:44} {note}")
    changed_pages = [r for r in rows if r[0] != r[0] or r[0] > args.fail_over]
    print(f"\n{len(rows)} shots compared, {len(changed_pages)} above the {args.fail_over}% threshold")
    if out:
        print(f"composites written to {out}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    capture = sub.add_parser("capture", help="render pages from this checkout and screenshot them")
    capture.add_argument("--out", required=True, help="output directory (created; artifacts land here)")
    capture.add_argument("--project-dir", default=None, help="checkout root to render (default: cwd)")
    capture.add_argument("--project-name", default="date", help="PROJECT_NAME / association variant")
    capture.add_argument("--unfold", action="store_true", help="render with USE_UNFOLD=True")
    capture.add_argument(
        "--model", action="append", default=[], help=f"app.Model to capture (default: {', '.join(DEFAULT_MODELS)})"
    )
    capture.add_argument("--url", action="append", default=[], help="extra LABEL=/path page")
    capture.add_argument("--width", type=int, default=WIDTH, help=f"viewport width (default {WIDTH})")
    capture.add_argument(
        "--heights", default=",".join(str(h) for h in HEIGHTS), help="comma separated viewport heights"
    )
    capture.add_argument("--chrome", default=None, help="path to a Chromium binary")
    capture.add_argument("--no-screenshot", action="store_true", help="render HTML and static only")
    capture.add_argument("--no-clean", dest="clean", action="store_false", help="keep an existing output directory")
    capture.set_defaults(func=cmd_capture)

    compare = sub.add_parser("compare", help="pixel-diff two capture directories")
    compare.add_argument("--base", required=True)
    compare.add_argument("--candidate", required=True)
    compare.add_argument("--out", default=None, help="write side-by-side and diff images here")
    compare.add_argument(
        "--threshold", type=int, default=8, help="per-channel delta that counts as changed (default 8)"
    )
    compare.add_argument("--fail-over", type=float, default=0.05, help="report pages above this changed percentage")
    compare.add_argument("--all-composites", action="store_true", help="write composites even for identical pages")
    compare.set_defaults(func=cmd_compare)

    args = parser.parse_args(argv)
    if args.command == "capture" and not args.model:
        args.model = list(DEFAULT_MODELS)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
