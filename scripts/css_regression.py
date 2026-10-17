#!/usr/bin/env python
"""Capture the rendered look of a running association site and prove a later capture is identical.

Why this exists: a CSS refactor changes shared stylesheets that six associations
render through different templates, so a stylesheet diff cannot tell a reviewer
whether anything a visitor sees has moved. This harness turns "nothing changed"
into a measurable claim: capture the site before the refactor, capture it after,
compare, and accept the change only when the comparison is clean.

Two channels are recorded per page and viewport, because they explain each other:

* a full-page PNG, which shows what a visitor sees, and
* a JSON snapshot of a fixed subset of computed styles for every element, which
  names the property that moved when a pixel moved, and also catches changes that
  are invisible in a static unfocused screenshot (a removed `outline: none`).

Usage:

    uv run python scripts/css_regression.py capture --label before
    uv run python scripts/css_regression.py capture --label after
    uv run python scripts/css_regression.py compare --before ~/.cache/date-website/css-regression/before \
--after ~/.cache/date-website/css-regression/after

Captures land in ~/.cache/date-website/css-regression/<label>/ unless --out names a
directory instead (--out is the capture directory itself, the label is then only a
note in the manifest). `capture --only date` limits a run to one variant, `--base
sf=http://127.0.0.1:8015` remaps a variant URL, and `--pages FILE` replaces the seed
list and the detail-page discovery with an explicit list (see
scripts/css_regression_pages.example.txt). A narrow viewport is not phone emulation:
the mobile viewport is a 390 CSS pixel wide desktop render, which is deterministic and
is what a CSS breakpoint test needs.

Live content that changes between two captures:

A few pages render content that changes on its own: a wall clock refreshed by a timer, or
a relative time such as "39 minuter sedan" computed server side from the request time.
Those pixels differ between any two captures, so such a page can never reach a green
verdict even when the stylesheet change is appearance-neutral. `--mask CSS_SELECTOR`
(repeatable) sets `visibility: hidden` on every element matching the selector, after the
page has settled and after the computed-style probe, and before the screenshot, so those
pixels stop being compared while the rest of the page keeps being compared:

    uv run python scripts/css_regression.py capture --label after --mask '#some-id'

`visibility: hidden` is used and never `display: none`: `display: none` takes the element
out of layout and shifts everything below it, which makes two captures differ for a
reason that is not the stylesheet. A match that has no layout box of its own is left in
place and the document is not otherwise changed. The mask is applied identically in every
capture. The style channel is unaffected by masking, because the probe runs before the
mask is applied: the computed properties of a masked element, and of everything inside
it, are compared exactly as the page built them, and only the masked pixels are ignored.
Masking is for live content only, not for hiding a difference a reviewer should see. The
selectors are
recorded in manifest.json together with the number of elements each matched per view, and
a selector that matches nothing is warned about instead of being assumed to have worked.

Signing in for a capture:

    CSS_REGRESSION_USERNAME=<user> CSS_REGRESSION_PASSWORD=<password> \
        uv run python scripts/css_regression.py capture --label after

Pages behind `login_required` are the reason this exists: signed out, such a page
redirects to the sign-in page, and the harness would then record the sign-in page as if
it were the page that was asked for, so a diff could compare two sign-in pages and call
the stylesheet neutral. Credentials come from --username/--password or, when those
flags are absent, from the CSS_REGRESSION_USERNAME and CSS_REGRESSION_PASSWORD
environment variables (prefer the environment: a --password value is visible in the
process list). When neither source has both values the capture stays anonymous, exactly
as before, and does not fail.

With credentials the harness signs in once per variant, before that variant's page
loop, by filling the sign-in form in the page over Runtime.evaluate and submitting it,
so the browser sends the CSRF token and keeps the session cookie. It then loads
--require-login-path (default /members/info/), a path that is only reachable when
signed in, and checks that it did not land back on --login-path (default
/members/login/) and that the status is 200. If that check fails the variant is
aborted with an error and none of its pages are captured: once credentials were
supplied there is never a silent fallback to an anonymous capture. Each variant's
sign-in result is recorded in manifest.json as variants.<name>.login, and every
captured page whose final URL path differs from the requested path carries a warning
in its entry, so a redirect to a sign-in page is visible in the report.

A gated page captured without credentials is therefore a capture of the sign-in page
rather than of the page that was asked for; the login object and the per-page warning
make that visible instead of silent.

compare refuses to run when the two captures resolved different page sets, when the
same page label resolved to a different path, or when they were taken at different
viewports (exit code 2), then reports per page and viewport the differing pixel count
and percentage, the difference bounding box, elements present only in one capture,
and every computed property whose value changed with both values. A view fails when
it exceeds either --tolerance (differing pixels, default 0) or --max-percent
(default 0.0), or, unless --allow-style-changes is given, when any computed style
changed. It writes comparison.json to the after directory (override with --out),
plus an amplified diff PNG per changed view under diffs/, and exits 1 when anything
failed, so it can gate a workflow. --list-only is the cheap mode: the summary table
and the severity grouping only, with no diff images and no per-property dump.

Exit codes: 0 identical, 1 differences found or capture errors, 2 bad input or
incomparable captures, 3 the browser session failed.

Two captures of the same unchanged site are byte-identical, which is the property the
whole gate rests on, so the capture is hermetic: animations and transitions are
disabled from document start (the pixel channel is therefore blind to them and the
computed-style channel covers them), the viewport, media features and device scale
factor are pinned, and the one third-party endpoint that answers with random content
each request is blocked (see UNSTABLE_URL_PATTERNS).

The site is driven over the Chrome DevTools Protocol on a raw WebSocket; no
Playwright or Selenium module is involved. Chrome is discovered the same way as in
scripts/visual_check.py, and can be overridden with --chrome or CHROME_PATH.
"""

from __future__ import annotations

import argparse
import base64
import glob
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, NoReturn

from PIL import Image, ImageChops
from websockets.exceptions import ConnectionClosed
from websockets.sync.client import ClientConnection, connect

# --------------------------------------------------------------------------
# configuration
# --------------------------------------------------------------------------

DEFAULT_STORE = Path.home() / ".cache" / "date-website" / "css-regression"

# The multi-association stack this harness was written for, one container port per
# variant. This mapping is deliberately not the repo's usual one (docker-compose.dev-all.yml
# puts sf and impuls on 8005 and 8006): a concurrent stack owns those ports, so the
# datecss stack publishes sf on 8015 and impuls on 8016. Verified with
# `docker inspect datecss-web-sf-1` (binds 8015) and `docker inspect datecss-web-impuls-1`
# (binds 8016). Override any entry with `--base name=http://host:port`.
# `demo` is excluded on purpose: it is slated for deletion and is not part of the
# parity claim, so capturing it would only add noise nobody acts on.
DEFAULT_BASE_URLS: dict[str, str] = {
    "date": "http://127.0.0.1:8002",
    "biocum": "http://127.0.0.1:8001",
    "kk": "http://127.0.0.1:8003",
    "pulterit": "http://127.0.0.1:8004",
    "sf": "http://127.0.0.1:8015",
    "impuls": "http://127.0.0.1:8016",
}
EXCLUDED_VARIANTS = {"demo"}

# Optional authentication for gated pages. The sign-in page is the two_factor login
# template (templates/common/members/registration/login.html, driven by
# members.two_factor.MemberLoginView), whose form carries the CSRF token and the
# username/password inputs this harness fills. The require-login path is a page that
# only resolves to itself when signed in, so it proves the session took effect.
DEFAULT_LOGIN_PATH = "/members/login/"
DEFAULT_REQUIRE_LOGIN_PATH = "/members/info/"
USERNAME_ENV_VAR = "CSS_REGRESSION_USERNAME"
PASSWORD_ENV_VAR = "CSS_REGRESSION_PASSWORD"


VIEWPORTS: dict[str, tuple[int, int]] = {"desktop": (1600, 1000), "mobile": (390, 844)}

# The fixed page set. Detail pages are discovered from the listing pages, never
# hardcoded, so a fixture change does not need a change here.
SEED_PAGES: tuple[tuple[str, str], ...] = (
    ("home", "/"),
    ("events", "/events/"),
    ("news", "/news/"),
    ("publications", "/publications/"),
    ("members-signup", "/members/signup/"),
    ("forms", "/forms/"),
    ("polls", "/polls/"),
    ("booking", "/booking/"),
)

# (section, listing path, detail href pattern, how many to keep). The patterns follow
# the URLconfs in this repo rather than a digits-only guess: events.EventDetailView
# takes a slug (`/events/<slug>/`, see events/urls.py), news article detail is
# `/news/articles/<slug>/` or `/news/<category>/<slug>/` (news/urls.py), and
# publications exposes a collection page (`/publications/<collection>/`) and a PDF
# view one level deeper (publications/urls.py). The patterns exclude the listing
# paths themselves.
DETAIL_SOURCES: tuple[tuple[str, str, re.Pattern[str], int], ...] = (
    ("events", "/events/", re.compile(r"^/events/[^/]+/$"), 2),
    ("news", "/news/", re.compile(r"^/news/(?:articles/[^/]+|[^/]+/[^/]+)/$"), 2),
    ("publications", "/publications/", re.compile(r"^/publications/[^/]+(?:/[^/]+)?/$"), 2),
)

# The computed-style property subset. Kept fixed so two captures are comparable
# element by element and property by property.
STYLE_PROPERTIES: tuple[str, ...] = (
    "display",
    "position",
    "top",
    "right",
    "bottom",
    "left",
    "z-index",
    "width",
    "height",
    "min-width",
    "min-height",
    "max-width",
    "max-height",
    "margin-top",
    "margin-right",
    "margin-bottom",
    "margin-left",
    "padding-top",
    "padding-right",
    "padding-bottom",
    "padding-left",
    "border-top-width",
    "border-right-width",
    "border-bottom-width",
    "border-left-width",
    "border-top-color",
    "border-right-color",
    "border-bottom-color",
    "border-left-color",
    "border-top-style",
    "border-radius",
    "background-color",
    "background-image",
    "color",
    "font-family",
    "font-size",
    "font-weight",
    "font-style",
    "line-height",
    "letter-spacing",
    "text-align",
    "text-decoration-line",
    "text-transform",
    "opacity",
    "visibility",
    "overflow-x",
    "overflow-y",
    "transform",
    "filter",
    "box-shadow",
    "grid-template-areas",
    "grid-template-columns",
    "grid-template-rows",
    "gap",
    "flex-direction",
    "flex-wrap",
    "justify-content",
    "align-items",
    "order",
    "transition-property",
    "cursor",
    "outline-style",
    "outline-width",
    "outline-color",
    "outline-offset",
    "border-right-style",
    "border-bottom-style",
    "border-left-style",
    "background-attachment",
    "background-position",
    "background-size",
    "background-repeat",
    "box-sizing",
    "float",
    "clear",
    "vertical-align",
    "table-layout",
    "border-collapse",
    "border-spacing",
    "caption-side",
    "flex-grow",
    "flex-shrink",
    "flex-basis",
    "align-self",
    "align-content",
    "justify-self",
    "justify-items",
    "grid-column-start",
    "grid-column-end",
    "grid-row-start",
    "grid-row-end",
    "grid-auto-flow",
    "list-style-type",
    "scale",
    "rotate",
    "translate",
    "row-gap",
    "column-gap",
    "white-space",
    "text-indent",
    "text-overflow",
    "text-shadow",
    "text-underline-offset",
    "word-break",
    "overflow-wrap",
    "hyphens",
    "aspect-ratio",
    "object-fit",
    "object-position",
    "clip-path",
    "backdrop-filter",
    "transform-origin",
    "transform-style",
    "perspective",
    "perspective-origin",
    "backface-visibility",
    "isolation",
    "pointer-events",
    "user-select",
    "resize",
    "scroll-behavior",
    "overscroll-behavior",
    "will-change",
    "content",
    "break-inside",
    "break-after",
    "color-scheme",
    "accent-color",
    "font-stretch",
    "font-variant-caps",
    "font-variant-ligatures",
    "font-variant-numeric",
    "font-variant-east-asian",
    "fill",
    "fill-opacity",
    "fill-rule",
    "stroke",
    "stroke-width",
    "stroke-opacity",
    "stroke-dasharray",
    "stroke-dashoffset",
    "stroke-linecap",
    "stroke-linejoin",
)

# Severity split for the style report. A property is "cosmetic metadata" when a
# static, unfocused screenshot cannot show it either way: the font stack (the
# rendered pixels come from the file that actually loaded, not from the list), the
# transition list, the cursor shape, and the outline, which only paints on focus.
# Everything else counts as "geometry or colour". The split is advisory output only:
# the exit code treats every style difference as a failure unless --allow-style-changes.
COSMETIC_PROPERTIES = frozenset(
    {"font-family", "transition-property", "cursor", "outline-style", "outline-width", "outline-color"}
)

# Injected at document start on every navigation. Animations and transitions are
# disabled so that a carousel, a hero entrance animation or a hover timing cannot
# produce false differences, and the caret is hidden so a blinking cursor cannot
# either. This makes the pixel channel blind to animation and transition changes on
# purpose; the computed-style channel covers those instead, which is why
# transition-duration/transition-delay are zeroed rather than the `transition`
# shorthand being set to `none`: the shorthand would also flatten the computed
# transition-property to `none` and hide exactly the signal the style diff reports.
OVERRIDE_STYLE_ID = "css-regression-overrides"
OVERRIDE_CSS = (
    "*, *::before, *::after {"
    " animation: none !important;"
    " transition-duration: 0s !important;"
    " transition-delay: 0s !important;"
    " caret-color: transparent !important;"
    "}"
)
INIT_SCRIPT = """
(() => {
  const CSS = __CSS__;
  const ID = __ID__;
  const install = () => {
    if (document.getElementById(ID)) return true;
    const parent = document.head || document.documentElement;
    if (!parent) return false;
    const style = document.createElement('style');
    style.id = ID;
    style.textContent = CSS;
    parent.appendChild(style);
    return true;
  };
  // Document start: the element that will own the stylesheets may not exist yet,
  // so retry on the first parser insertion instead of waiting for DOMContentLoaded,
  // which would be late enough for an entrance animation to have started.
  if (!install()) {
    new MutationObserver((records, observer) => { if (install()) observer.disconnect(); })
      .observe(document, {childList: true, subtree: true});
  }
})()
""".replace("__CSS__", json.dumps(OVERRIDE_CSS)).replace("__ID__", json.dumps(OVERRIDE_STYLE_ID))

# Fill and submit the sign-in form from inside the page, over Runtime.evaluate rather
# than synthesised key events, so the browser itself applies the field values and sends
# the hidden CSRF token that the rendered form already carries. The field names are
# discovered from the form rather than hardcoded: the login form is a two_factor wizard
# whose authentication step renders `auth-username` and `auth-password` next to a hidden
# `member_login_view-current_step` field, and a name lookup survives a prefix change.
# The fields are set first and the submit is deferred by one tick, so the evaluate call
# returns its (password-free) summary before the navigation destroys the context.
LOGIN_FILL_FN = """
function (username, password) {
  const passwordField = document.querySelector('input[type="password"]');
  if (!passwordField) return JSON.stringify({ok: false, error: 'the page has no password field, so it is not a sign-in form'});
  const form = passwordField.form;
  if (!form) return JSON.stringify({ok: false, error: 'the password field is not inside a form'});
  let usernameField = null;
  for (const element of form.elements) {
    if (element === passwordField) continue;
    const type = (element.getAttribute('type') || 'text').toLowerCase();
    if (type !== 'text' && type !== 'email') continue;
    const name = (element.name || '').toLowerCase();
    if (name === 'username' || name.endsWith('-username') || name.endsWith('username')) { usernameField = element; break; }
  }
  if (!usernameField) return JSON.stringify({ok: false, error: 'the sign-in form has no username field'});
  usernameField.value = username;
  passwordField.value = password;
  const summary = {
    ok: true,
    username_field: usernameField.name,
    password_field: passwordField.name,
    action: passwordField.form.getAttribute('action') || location.pathname,
  };
  setTimeout(() => {
    if (typeof form.requestSubmit === 'function') form.requestSubmit();
    else form.submit();
  }, 0);
  return JSON.stringify(summary);
}
"""

# One pass over every element: the DOM path key, the fixed property subset, and the
# page level facts that belong with the snapshot. Returned as a JSON string so the
# result comes back by value in a single round trip.
PROBE_JS = """
(() => {
  const properties = __PROPERTIES__;
  const path = (element) => {
    const parts = [];
    let node = element;
    while (node && node.nodeType === 1 && node.tagName.toLowerCase() !== 'html') {
      const tag = node.tagName.toLowerCase();
      const parent = node.parentElement;
      let index = 1;
      if (parent) {
        for (const sibling of parent.children) {
          if (sibling === node) break;
          if (sibling.tagName.toLowerCase() === tag) index += 1;
        }
      }
      parts.unshift(tag + ':nth-of-type(' + index + ')');
      node = parent;
    }
    parts.unshift('html');
    return parts.join('>');
  };
  const elements = [];
  let animated = 0;
  // Stylesheet links in document order. Inline <style> blocks have no URL of their
  // own and the injected override style is deliberately left out, so the list is
  // exactly what the page asked the browser to load.
  const stylesheetLinks = [];
  for (const link of document.querySelectorAll('link[rel~="stylesheet"]')) {
    stylesheetLinks.push(link.href);
  }
  for (const element of document.querySelectorAll('*')) {
    const computed = window.getComputedStyle(element);
    if (computed.animationName !== 'none') animated += 1;
    const snapshot = {};
    for (const name of properties) snapshot[name] = computed.getPropertyValue(name);
    elements.push({k: path(element), s: snapshot});
  }
  return JSON.stringify({
    url: location.href,
    title: document.title,
    stylesheets: stylesheetLinks,
    scrollWidth: document.documentElement.scrollWidth,
    scrollHeight: document.documentElement.scrollHeight,
    animated: animated,
    elements: elements,
  });
})()
""".replace("__PROPERTIES__", json.dumps(list(STYLE_PROPERTIES)))

# Set `visibility: hidden` on every element matching each --mask selector, and report how
# many elements each selector matched. `visibility: hidden` rather than `display: none`:
# `display: none` removes the element from layout and shifts everything below it, which
# would make two captures differ for a reason that is not the stylesheet under test. The
# element is otherwise left alone, including a match that has no layout box of its own:
# nothing is wrapped, moved, removed or otherwise changed. Run after the settle and after
# the computed-style probe, so the style channel records the unmasked document, and before
# the screenshot, so only the pixels of the live content are dropped.
MASK_JS = """
(() => {
  const selectors = __SELECTORS__;
  const counts = {};
  const errors = {};
  for (const selector of selectors) {
    let matches;
    try {
      matches = document.querySelectorAll(selector);
    } catch (error) {
      errors[selector] = String(error);
      continue;
    }
    for (const element of matches) {
      element.style.setProperty('visibility', 'hidden', 'important');
    }
    counts[selector] = matches.length;
  }
  return JSON.stringify({counts: counts, errors: errors});
})()
"""

FRAME_JS = "new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(() => resolve('frame'))))"
FONTS_JS = "document.fonts.ready.then(() => 'fonts')"
SETTLE_JS = """
new Promise((resolve) => {
  const quiet = __QUIET__;
  const cap = __CAP__;
  const target = document.documentElement;
  if (!target) { resolve('no-document-element'); return; }
  let quietTimer = null;
  let capTimer = null;
  let finished = false;
  const observer = new MutationObserver(() => {
    clearTimeout(quietTimer);
    quietTimer = setTimeout(() => finish('quiet'), quiet);
  });
  const finish = (reason) => {
    if (finished) return;
    finished = true;
    clearTimeout(quietTimer);
    clearTimeout(capTimer);
    observer.disconnect();
    resolve(reason);
  };
  observer.observe(target, {childList: true, subtree: true, attributes: true, characterData: true});
  quietTimer = setTimeout(() => finish('quiet'), quiet);
  capTimer = setTimeout(() => finish('capped'), cap);
})
"""

SETTLE_QUIET_MS = 300
SETTLE_CAP_MS = 5000
NETWORK_IDLE_MS = 500
NETWORK_IDLE_TIMEOUT = 15.0
FONTS_TIMEOUT = 20.0
DIFF_AMPLIFY = 8
USER_AGENT = "css-regression/1.0 (+scripts/css_regression.py)"

# Content that cannot be part of a parity claim because it is random on every request.
# The homepage fetches a random joke from icanhazdadjoke.com and injects it into
# #joke-string (templates/date/date/components/scripts.html, and the same snippet for
# pulterit), which changes both the text and, when the line count changes, the height
# of the paragraph above the fold. Blocking the request lets the page's own error
# branch run, so the element is empty in every capture and the comparison stays about
# CSS. The list is recorded in the manifest so a reader can see what was excluded.
UNSTABLE_URL_PATTERNS: tuple[str, ...] = ("*icanhazdadjoke.com*",)

# Copied from scripts/visual_check.py so both scripts find the same Chromium.
CHROME_GLOBS = (
    "~/.cache/ms-playwright/chromium-*/chrome-linux64/chrome",
    "~/.cache/ms-playwright/chromium-*/chrome-linux/chrome",
    "~/.cache/ms-playwright/chromium_headless_shell-*/chrome-headless-shell-linux64/chrome-headless-shell",
)
CHROME_NAMES = ("chromium", "chromium-browser", "google-chrome", "google-chrome-stable")

HREF_RE = re.compile(r"""href\s*=\s*(?:"([^"]*)"|'([^']*)')""", re.IGNORECASE)


def fail(message: str) -> NoReturn:
    """Abort a run that cannot produce a comparison, with exit code 2.

    Exit codes are 0 for identical, 1 for differences found, 2 for bad input or
    incomparable captures, and 3 for a broken browser session.
    """
    print(f"error: {message}", file=sys.stderr)
    raise SystemExit(2)


def find_chrome(explicit: str | None) -> str:
    """Locate a Chromium binary: --chrome, then CHROME_PATH, then PATH, then Playwright."""
    if explicit:
        if not Path(explicit).exists():
            fail(f"--chrome {explicit} does not exist")
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
    fail("No Chromium found. Install one, set CHROME_PATH, or pass --chrome /path/to/chrome.")


# --------------------------------------------------------------------------
# HTTP helpers (page resolution only; the pages themselves are fetched by Chrome)
# --------------------------------------------------------------------------


def http_fetch(
    url: str, *, timeout: float = 20.0, attempts: int = 3, retry_404: bool = False
) -> tuple[int | None, str, str]:
    """GET a URL with a bounded retry.

    Returns (status, body, final_url); status is None when every attempt failed at the
    transport level. Retries cover the case where the stack is still loading fixtures:
    the brief for this harness says a page that 404s or is empty at the start may just
    need a moment. A 5xx is always retried, a 404 only when retry_404 is set.
    """
    last_error = "unknown error"
    for attempt in range(1, attempts + 1):
        request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return int(response.status), response.read().decode("utf-8", "replace"), response.url
        except urllib.error.HTTPError as error:
            body = error.read().decode("utf-8", "replace")
            if error.code < 500 and not (retry_404 and error.code == 404):
                return int(error.code), body, error.url or url
            last_error = f"HTTP {error.code}"
        except (urllib.error.URLError, TimeoutError, OSError) as error:
            last_error = str(error)
        if attempt < attempts:
            print(f"    {url}: {last_error}, retrying")
            time.sleep(5.0)
    print(f"    {url}: giving up after {attempts} attempts ({last_error})")
    return None, "", url


def iter_hrefs(html: str) -> Iterator[str]:
    for match in HREF_RE.finditer(html):
        value = match.group(1) if match.group(1) is not None else match.group(2)
        yield value.strip()


def path_of(url: str) -> str:
    parts = urllib.parse.urlsplit(url)
    return parts.path + (f"?{parts.query}" if parts.query else "")


def normalized_path(url: str) -> str:
    """The path of a URL without its query and without a trailing slash, so /a/ equals /a.

    Used to decide whether a navigation ended on the page that was asked for: a sign-in
    redirect adds a `?next=` query, which must not hide that the browser is on the login
    page.
    """
    path = urllib.parse.urlsplit(url).path or "/"
    return path.rstrip("/") or "/"


def match_detail_hrefs(html: str, page_url: str, pattern: re.Pattern[str], limit: int) -> tuple[list[str], int]:
    """Pick the first `limit` same-origin detail links, in document order.

    Document order makes the choice deterministic: the same fixtures always produce
    the same two detail pages. Returns (matched paths, number of same-origin hrefs seen).
    """
    origin = urllib.parse.urlsplit(page_url)
    matched: list[str] = []
    seen: list[str] = []
    scanned = 0
    for href in iter_hrefs(html):
        if not href or href.startswith("#"):
            continue
        resolved = urllib.parse.urlsplit(urllib.parse.urljoin(page_url, href))
        if resolved.scheme not in ("http", "https") or resolved.netloc != origin.netloc:
            continue
        scanned += 1
        candidate = path_of(urllib.parse.urljoin(page_url, href))
        if candidate in seen:
            continue
        seen.append(candidate)
        if pattern.match(resolved.path) and len(matched) < limit:
            matched.append(candidate)
    return matched, scanned


def label_from_path(path: str) -> str:
    """A stable page label derived from a path, e.g. /members/signup/ -> members-signup."""
    cleaned = re.sub(r"[^a-z0-9]+", "-", path.split("?", 1)[0].lower()).strip("-")
    return cleaned or "home"


def read_pages_file(pages_file: str) -> list[tuple[str, str]]:
    """Read an explicit page list: one path per line, blank lines and # comments skipped."""
    lines = Path(pages_file).expanduser().read_text(encoding="utf-8").splitlines()
    pages: list[tuple[str, str]] = []
    used: set[str] = set()
    for line in lines:
        path = line.split("#", 1)[0].strip()
        if not path:
            continue
        if not path.startswith("/"):
            fail(f"{pages_file}: every page path must start with /, got {path!r}")
        label = label_from_path(path)
        if label in used:
            suffix = 2
            while f"{label}-{suffix}" in used:
                suffix += 1
            label = f"{label}-{suffix}"
        used.add(label)
        pages.append((label, path))
    if not pages:
        fail(f"{pages_file}: no page paths found")
    return pages


def resolve_pages(base_url: str, pages_file: str | None) -> tuple[list[tuple[str, str]], dict[str, Any]]:
    """Resolve the page set for one variant, recording where each page came from."""
    if pages_file:
        return read_pages_file(pages_file), {"source": "file", "file": str(Path(pages_file).expanduser())}

    pages = list(SEED_PAGES)
    taken = {path for _, path in pages}
    discovery: dict[str, Any] = {"source": "seeds+discovery", "listings": {}}
    for section, listing, pattern, limit in DETAIL_SOURCES:
        listing_url = base_url + listing
        status, body, final_url = http_fetch(listing_url, retry_404=True)
        matched, scanned = (
            match_detail_hrefs(body or "", final_url or listing_url, pattern, limit) if status == 200 else ([], 0)
        )
        record: dict[str, Any] = {
            "status": status,
            "final_url": final_url,
            "same_origin_hrefs": scanned,
            "matched": matched,
        }
        discovery["listings"][listing] = record
        for index, path in enumerate(matched, start=1):
            if path in taken:
                continue
            taken.add(path)
            pages.append((f"{section}-detail-{index}", path))
    return pages, discovery


# --------------------------------------------------------------------------
# Chrome and the DevTools Protocol
# --------------------------------------------------------------------------


class CdpError(RuntimeError):
    """A DevTools command failed or timed out."""


class CdpConnection:
    """Minimal Chrome DevTools Protocol client: request/response matching plus events.

    Only what this harness needs: send a command, match the response by id, and hand
    every event to the listeners so network and load tracking can run alongside.
    """

    def __init__(self, websocket: ClientConnection) -> None:
        self._ws = websocket
        self._next_id = 0
        self._events: list[dict[str, Any]] = []
        self._listeners: list[Callable[[dict[str, Any]], None]] = []

    def add_listener(self, listener: Callable[[dict[str, Any]], None]) -> None:
        self._listeners.append(listener)

    def clear_events(self) -> None:
        self._events.clear()

    def call(self, method: str, params: dict[str, Any] | None = None, timeout: float = 30.0) -> dict[str, Any]:
        self._next_id += 1
        request_id = self._next_id
        payload: dict[str, Any] = {"id": request_id, "method": method}
        if params:
            payload["params"] = params
        self._ws.send(json.dumps(payload))
        deadline = time.monotonic() + timeout
        while True:
            message = self._receive(deadline, method)
            if message.get("id") == request_id:
                if "error" in message:
                    raise CdpError(f"{method}: {message['error'].get('message', message['error'])}")
                return message.get("result") or {}
            self._dispatch(message)

    def wait_for_event(self, method: str, *, frame_id: str | None = None, timeout: float = 30.0) -> dict[str, Any]:
        for index, event in enumerate(self._events):
            if event.get("method") == method and _frame_matches(event, frame_id):
                return self._events.pop(index)
        deadline = time.monotonic() + timeout
        while True:
            message = self._receive(deadline, method)
            if message.get("method") == method and _frame_matches(message, frame_id):
                return message
            self._dispatch(message)

    def pump(self, timeout: float) -> None:
        """Read at most one message, feeding listeners; returns quietly on timeout."""
        try:
            raw = self._ws.recv(timeout=max(0.001, timeout))
        except TimeoutError:
            return
        self._dispatch(json.loads(raw))

    def _receive(self, deadline: float, context: str) -> dict[str, Any]:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise CdpError(f"{context}: timed out waiting for a DevTools response")
        try:
            raw = self._ws.recv(timeout=remaining)
        except TimeoutError as error:
            raise CdpError(f"{context}: timed out waiting for a DevTools response") from error
        except ConnectionClosed as error:
            raise CdpError(f"{context}: the browser connection closed ({error})") from error
        return json.loads(raw)

    def _dispatch(self, message: dict[str, Any]) -> None:
        if "method" not in message:
            return
        self._events.append(message)
        for listener in self._listeners:
            listener(message)


def _frame_matches(event: dict[str, Any], frame_id: str | None) -> bool:
    if frame_id is None:
        return True
    params = event.get("params") or {}
    if "frameId" not in params:
        # Not every event carries a frame id (Page.loadEventFired carries only a
        # timestamp), so an event that cannot be attributed is accepted rather than
        # being dropped and waited for forever.
        return True
    return params["frameId"] == frame_id


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def wait_for_devtools(port: int, process: subprocess.Popen[bytes], timeout: float = 30.0) -> None:
    deadline = time.monotonic() + timeout
    url = f"http://127.0.0.1:{port}/json/version"
    while time.monotonic() < deadline:
        if process.poll() is not None:
            fail(f"Chromium exited early with code {process.returncode} before its DevTools port opened")
        try:
            with urllib.request.urlopen(url, timeout=2.0):
                return
        except urllib.error.URLError, TimeoutError, OSError:
            time.sleep(0.25)
    fail(f"Chromium did not open a DevTools port on 127.0.0.1:{port} within {timeout:.0f}s")


@contextmanager
def launch_chrome(chrome: str) -> Iterator[int]:
    """Start one headless Chromium for the whole capture and yield its debug port.

    A fresh temporary profile per capture keeps runs independent; the profile is
    removed afterwards so nothing accumulates outside the capture store.
    """
    port = free_port()
    profile = Path(tempfile.mkdtemp(prefix="css-regression-chrome-"))
    log_path = profile / "chrome.log"
    command = [
        chrome,
        "--headless=new",
        f"--remote-debugging-port={port}",
        "--no-sandbox",
        "--disable-gpu",
        "--hide-scrollbars",
        # Pinned device scale factor: a scale factor of 2 would double every image and
        # make pixel counts depend on the host, not on the CSS.
        "--force-device-scale-factor=1",
        f"--user-data-dir={profile}",
        "--disable-dev-shm-usage",
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-extensions",
        "--disable-background-networking",
        # Deterministic rasterisation. Each of these removes a source of variance
        # between two captures of an unchanged tree, which the pixel channel needs
        # to be usable as a gate: compositor stage timing, threaded animation and
        # scrolling, checkerboard imaging, the content rendering timeout, and font
        # hinting or LCD text. The observed case that forced this was the
        # backdrop-filter corner on the seasonal event sheets landing a few pixels
        # differently, with no computed style changing at all.
        "--deterministic-mode",
        "--run-all-compositor-stages-before-draw",
        "--disable-threaded-animation",
        "--disable-threaded-scrolling",
        "--disable-checker-imaging",
        "--disable-new-content-rendering-timeout",
        "--disable-image-animation-resync",
        "--font-render-hinting=none",
        "--disable-lcd-text",
    ]
    with log_path.open("wb") as log_handle:
        try:
            process = subprocess.Popen(command, stdout=log_handle, stderr=subprocess.STDOUT)
        except OSError as error:
            shutil.rmtree(profile, ignore_errors=True)
            fail(f"could not start {chrome}: {error}")
    try:
        wait_for_devtools(port, process)
        yield port
    finally:
        stop_chrome(process)
        remove_profile(profile)


def stop_chrome(process: subprocess.Popen[bytes]) -> None:
    process.terminate()
    try:
        process.wait(timeout=15)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=15)


def remove_profile(profile: Path) -> None:
    """Remove the temporary Chrome profile, retrying briefly.

    Chrome's helper processes (zygote, renderer, network service) can outlive the
    browser process for a moment and recreate a directory while it is being removed,
    which leaves an empty profile behind on every run. One retry loop is enough and
    keeps the run clean for the next caller.
    """
    for _ in range(3):
        shutil.rmtree(profile, ignore_errors=True)
        if not profile.exists():
            return
        time.sleep(0.5)
    shutil.rmtree(profile, ignore_errors=True)


def create_page_target(port: int) -> str:
    """Open a page target and return its WebSocket URL.

    One page target per variant session, reused for every page and viewport of that
    variant, so the per-page cost is a navigation rather than a new connection.
    """
    request = urllib.request.Request(f"http://127.0.0.1:{port}/json/new?about:blank", method="PUT")
    try:
        with urllib.request.urlopen(request, timeout=10.0) as response:
            target = json.load(response)
        ws_url = target.get("webSocketDebuggerUrl")
        if ws_url:
            return str(ws_url)
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError, ValueError) as error:
        print(f"    could not create a page target ({error}), falling back to an existing tab")
    listing = urllib.request.urlopen(f"http://127.0.0.1:{port}/json/list", timeout=10.0)
    with listing:
        targets = json.load(listing)
    for target in targets:
        if target.get("type") == "page" and target.get("webSocketDebuggerUrl"):
            return str(target["webSocketDebuggerUrl"])
    fail("Chromium exposed no page target to drive")


@contextmanager
def open_variant_session(port: int) -> Iterator[CdpConnection]:
    ws_url = create_page_target(port)
    # websockets 17 requires connect() to be used as a context manager (or legacy=True).
    with connect(ws_url, max_size=None, open_timeout=30.0) as websocket:
        connection = CdpConnection(websocket)
        connection.call("Page.enable")
        connection.call("Runtime.enable")
        connection.call("Network.enable")
        connection.call("Page.addScriptToEvaluateOnNewDocument", {"source": INIT_SCRIPT})
        # Drop the third-party content that is random per request; see UNSTABLE_URL_PATTERNS.
        connection.call("Network.setBlockedURLs", {"urls": list(UNSTABLE_URL_PATTERNS)})
        # Pin the media features so a host-level dark mode or reduced motion preference
        # cannot leak into a capture and make two runs differ.
        connection.call(
            "Emulation.setEmulatedMedia",
            {
                "features": [
                    {"name": "prefers-color-scheme", "value": "light"},
                    {"name": "prefers-reduced-motion", "value": "reduce"},
                ]
            },
        )
        yield connection


@dataclass
class NetworkTracker:
    """Track in-flight requests so a page is captured after the network has settled."""

    pending: set[str] = field(default_factory=set)
    document_responses: list[dict[str, Any]] = field(default_factory=list)
    last_event: float = field(default_factory=time.monotonic)

    def reset(self) -> None:
        self.pending.clear()
        self.document_responses.clear()
        self.last_event = time.monotonic()

    def handle(self, message: dict[str, Any]) -> None:
        method = message.get("method") or ""
        if not method.startswith("Network."):
            return
        params = message.get("params") or {}
        request_id = params.get("requestId")
        if method == "Network.requestWillBeSent" and request_id:
            self.pending.add(str(request_id))
            self.last_event = time.monotonic()
        elif method in ("Network.loadingFinished", "Network.loadingFailed") and request_id:
            self.pending.discard(str(request_id))
            self.last_event = time.monotonic()
        elif method == "Network.responseReceived" and params.get("type") == "Document":
            response = params.get("response") or {}
            self.document_responses.append({"status": response.get("status"), "url": response.get("url")})
            self.last_event = time.monotonic()


def wait_for_network_idle(connection: CdpConnection, tracker: NetworkTracker, timeout: float) -> bool:
    """Wait until no request has been in flight for NETWORK_IDLE_MS. False on timeout."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        connection.pump(timeout=min(0.25, max(0.001, deadline - time.monotonic())))
        if not tracker.pending and (time.monotonic() - tracker.last_event) * 1000 >= NETWORK_IDLE_MS:
            return True
    return False


def evaluate(connection: CdpConnection, expression: str, *, await_promise: bool = False, timeout: float = 30.0) -> Any:
    result = connection.call(
        "Runtime.evaluate",
        {"expression": expression, "returnByValue": True, "awaitPromise": await_promise},
        timeout=timeout,
    )
    if "exceptionDetails" in result:
        raise CdpError(f"page script failed: {result['exceptionDetails'].get('text')}")
    return (result.get("result") or {}).get("value")


def evaluate_handle(connection: CdpConnection, expression: str, *, timeout: float = 30.0) -> str | None:
    """Evaluate an expression and return a handle to the resulting object.

    A handle is what `call_function_on` needs, and that call takes its arguments as
    values rather than as script text, so a credential handed to the page is never
    part of a script source string.
    """
    result = connection.call(
        "Runtime.evaluate",
        {"expression": expression, "returnByValue": False},
        timeout=timeout,
    )
    if "exceptionDetails" in result:
        raise CdpError(f"page script failed: {result['exceptionDetails'].get('text')}")
    return (result.get("result") or {}).get("objectId")


def call_function_on(
    connection: CdpConnection,
    object_id: str,
    function_declaration: str,
    arguments: list[str],
    *,
    timeout: float = 30.0,
) -> Any:
    """Call a function on a page object, passing the arguments as values."""
    result = connection.call(
        "Runtime.callFunctionOn",
        {
            "objectId": object_id,
            "functionDeclaration": function_declaration,
            "arguments": [{"value": argument} for argument in arguments],
            "returnByValue": True,
        },
        timeout=timeout,
    )
    if "exceptionDetails" in result:
        raise CdpError(f"page script failed: {result['exceptionDetails'].get('text')}")
    return (result.get("result") or {}).get("value")


def navigate_and_settle(
    connection: CdpConnection, tracker: NetworkTracker, url: str, timeout: float
) -> tuple[int | None, str]:
    """Navigate, wait for the load event and the network, and report (status, final URL).

    The status is the last Document response of the redirect chain, which is the
    response that actually rendered, and the final URL is read from the page so a
    client-side redirect is seen as well. Raises CdpError when the navigation does not
    complete, which the login caller turns into a per-variant abort.
    """
    tracker.reset()
    connection.clear_events()
    navigation = connection.call("Page.navigate", {"url": url}, timeout=timeout)
    connection.wait_for_event("Page.loadEventFired", frame_id=navigation.get("frameId"), timeout=timeout)
    wait_for_network_idle(connection, tracker, min(NETWORK_IDLE_TIMEOUT, timeout))
    final_url = str(evaluate(connection, "location.href", timeout=min(10.0, timeout)))
    status = tracker.document_responses[-1]["status"] if tracker.document_responses else None
    return status, final_url


def submit_login_form(
    connection: CdpConnection,
    tracker: NetworkTracker,
    *,
    username: str,
    password: str,
    timeout: float,
) -> dict[str, Any]:
    """Fill and submit the sign-in form, then wait for the page it returns.

    Returns a dict with `ok` plus, on success, the field names that were filled and the
    status/final URL of the page that answered. The credentials are passed to the page as
    call arguments, never as script text, and they are not returned, printed or written
    to the manifest.
    """
    tracker.reset()
    connection.clear_events()
    document = evaluate_handle(connection, "document", timeout=timeout)
    if not document:
        return {"ok": False, "error": "the page has no document to fill"}
    filled = call_function_on(connection, document, LOGIN_FILL_FN, [username, password], timeout=timeout)
    payload: dict[str, Any] = json.loads(filled) if filled else {}
    if not payload.get("ok"):
        return {"ok": False, "error": str(payload.get("error") or "the sign-in form could not be filled")}
    try:
        connection.wait_for_event("Page.loadEventFired", timeout=timeout)
    except CdpError as error:
        return {"ok": False, "error": f"the sign-in form was submitted but no page load followed: {error}"}
    wait_for_network_idle(connection, tracker, min(NETWORK_IDLE_TIMEOUT, timeout))
    final_url = str(evaluate(connection, "location.href", timeout=min(10.0, timeout)))
    status = tracker.document_responses[-1]["status"] if tracker.document_responses else None
    return {
        "ok": True,
        "status": status,
        "final_url": final_url,
        "username_field": payload.get("username_field"),
        "password_field": payload.get("password_field"),
        "action": payload.get("action"),
    }


def login_variant(
    connection: CdpConnection,
    tracker: NetworkTracker,
    *,
    base_url: str,
    username: str,
    password: str,
    login_path: str,
    require_login_path: str,
    timeout: float,
) -> dict[str, Any]:
    """Sign in once for one variant and prove the session took effect.

    Navigates to the login path, submits the form, then loads the require-login path and
    checks that it did not land back on the login path and that it answered 200. The
    returned record is written to the manifest as variants.<name>.login. `verified` is
    False for a variant that must be aborted; the caller then captures none of its pages
    rather than falling back to an anonymous capture.
    """
    login_url = base_url + login_path
    require_url = base_url + require_login_path
    record: dict[str, Any] = {
        "used": True,
        "username": username,
        "status": None,
        "final_url": None,
        "verified": False,
        "login_path": login_path,
        "require_login_path": require_login_path,
        "login_status": None,
        "login_final_url": None,
        "fields": None,
        "error": None,
    }
    try:
        login_status, login_final_url = navigate_and_settle(connection, tracker, login_url, timeout)
    except CdpError as error:
        record["error"] = f"navigating to {login_path} failed: {error}"
        return record
    record["login_status"] = login_status
    record["login_final_url"] = login_final_url

    try:
        submitted = submit_login_form(connection, tracker, username=username, password=password, timeout=timeout)
    except CdpError as error:
        record["error"] = f"submitting the sign-in form at {login_path} failed: {error}"
        return record
    if not submitted.get("ok"):
        record["error"] = str(submitted.get("error"))
        return record
    record["fields"] = {
        "username": submitted.get("username_field"),
        "password": submitted.get("password_field"),
        "action": submitted.get("action"),
    }

    try:
        status, final_url = navigate_and_settle(connection, tracker, require_url, timeout)
    except CdpError as error:
        record["error"] = f"navigating to {require_login_path} after signing in failed: {error}"
        return record
    record["status"] = status
    record["final_url"] = final_url

    final_path = normalized_path(final_url)
    if final_path == normalized_path(login_url):
        record["error"] = (
            f"signing in did not take effect: {require_login_path} redirected to the login path {final_path}"
        )
    elif status != 200:
        record["error"] = f"signing in did not take effect: {require_login_path} returned status {status}"
    else:
        record["verified"] = True
    return record


def resolve_credentials(args: argparse.Namespace) -> tuple[str | None, str | None]:
    """Resolve the optional credentials from the flags, then the environment.

    Both absent means an anonymous capture, which is the pre-existing behaviour. Only one
    of the two present is a mistake that would otherwise be read as an authenticated run,
    so it fails rather than being ignored.
    """
    username = args.username or os.environ.get(USERNAME_ENV_VAR) or None
    password = args.password or os.environ.get(PASSWORD_ENV_VAR) or None
    if username and not password:
        # The env var names stay out of these messages: naming a password variable in a
        # string that reaches an error print is what CodeQL's clear-text rule reports,
        # even when the string is only the variable's name. --help lists both.
        fail("a username was supplied without a password; pass both, or set both environment variables")
    if password and not username:
        fail("a password was supplied without a username; pass both, or set both environment variables")
    return username, password


def apply_masks(
    connection: CdpConnection, selectors: list[str], *, timeout: float
) -> tuple[dict[str, int], dict[str, str]]:
    """Hide every element matching each mask selector, and count the matches per selector.

    Returns (matched elements per selector, selector errors). An unusable selector is
    reported rather than aborting the capture, so one typo does not lose a whole run.
    """
    expression = MASK_JS.replace("__SELECTORS__", json.dumps(list(selectors)))
    raw = evaluate(connection, expression, timeout=timeout)
    payload: dict[str, Any] = json.loads(raw) if raw else {}
    counts = {str(selector): int(count) for selector, count in (payload.get("counts") or {}).items()}
    errors = {str(selector): str(message) for selector, message in (payload.get("errors") or {}).items()}
    return counts, errors


def capture_page(
    connection: CdpConnection,
    tracker: NetworkTracker,
    *,
    url: str,
    png_path: Path,
    styles_path: Path,
    masks: list[str],
    timeout: float,
) -> dict[str, Any]:
    """Navigate one page, wait for it to settle, and record both channels."""
    started = time.monotonic()
    deadline = started + timeout
    warnings: list[str] = []

    def remaining() -> float:
        return max(1.0, deadline - time.monotonic())

    tracker.reset()
    connection.clear_events()
    try:
        navigation = connection.call("Page.navigate", {"url": url}, timeout=remaining())
        connection.wait_for_event("Page.loadEventFired", frame_id=navigation.get("frameId"), timeout=remaining())
    except CdpError as navigation_error:
        # One unreachable page must not abort the whole capture run.
        return {
            "error": f"navigation failed: {navigation_error}",
            "warnings": warnings,
            "seconds": round(time.monotonic() - started, 3),
        }

    if not wait_for_network_idle(connection, tracker, min(NETWORK_IDLE_TIMEOUT, remaining())):
        warnings.append(f"network did not go idle within {NETWORK_IDLE_TIMEOUT:.0f}s")

    # The override stylesheet is installed at document start (see INIT_SCRIPT); this
    # report of elements still animating is the check that it took effect.
    for expression, label, promise in (
        (FONTS_JS, "document.fonts.ready", True),
        (FRAME_JS, "animation frame", True),
    ):
        try:
            evaluate(connection, expression, await_promise=promise, timeout=min(FONTS_TIMEOUT, remaining()))
        except CdpError as readiness_error:
            warnings.append(f"{label}: {readiness_error}")

    settle_js = SETTLE_JS.replace("__QUIET__", str(SETTLE_QUIET_MS)).replace("__CAP__", str(SETTLE_CAP_MS))
    try:
        settle_reason = evaluate(connection, settle_js, await_promise=True, timeout=min(10.0, remaining()))
        if settle_reason == "capped":
            warnings.append(f"DOM kept mutating for {SETTLE_CAP_MS}ms, capturing anyway")
        elif settle_reason == "no-document-element":
            warnings.append("document element disappeared before the capture")
    except CdpError as error:
        warnings.append(f"settle: {error}")

    try:
        evaluate(connection, "window.scrollTo(0, 0)", timeout=min(10.0, remaining()))
        probe_raw = evaluate(connection, PROBE_JS, timeout=min(60.0, remaining()))
    except CdpError as error:
        return {
            "error": f"computed-style probe failed: {error}",
            "warnings": warnings,
            "seconds": round(time.monotonic() - started, 3),
        }

    probe = json.loads(probe_raw)
    styles_path.parent.mkdir(parents=True, exist_ok=True)
    styles_path.write_text(
        json.dumps(
            {
                "page": styles_path.stem,
                "url": probe["url"],
                "title": probe["title"],
                "stylesheets": probe["stylesheets"],
                "scroll_width": probe["scrollWidth"],
                "scroll_height": probe["scrollHeight"],
                "animated_elements": probe["animated"],
                "properties": list(STYLE_PROPERTIES),
                "elements": probe["elements"],
            },
            indent=1,
            sort_keys=False,
        )
        + "\n",
        encoding="utf-8",
    )
    if probe["animated"]:
        warnings.append(f"{probe['animated']} elements still report a CSS animation")

    # Mask the live content that cannot be part of a parity claim (see MASK_JS). This
    # runs after the computed-style probe and before the screenshot, so the style
    # channel sees the document as the page built it, including inside a masked
    # element, and only the pixels of the live content are dropped.
    masked: dict[str, int] = {}
    if masks:
        try:
            masked, mask_errors = apply_masks(connection, masks, timeout=min(30.0, remaining()))
        except CdpError as error:
            return {
                "error": f"applying --mask failed: {error}",
                "warnings": warnings,
                "seconds": round(time.monotonic() - started, 3),
            }
        for selector, message in mask_errors.items():
            warnings.append(f"--mask {selector!r} is not a usable CSS selector: {message}")
        try:
            # Let the paint catch up with the mask before the screenshot is taken.
            evaluate(connection, FRAME_JS, await_promise=True, timeout=min(10.0, remaining()))
        except CdpError as error:
            warnings.append(f"repaint after --mask: {error}")

    try:
        metrics = connection.call("Page.getLayoutMetrics", timeout=remaining())
    except CdpError as metrics_error:
        return {
            "error": f"layout metrics failed: {metrics_error}",
            "warnings": warnings,
            "seconds": round(time.monotonic() - started, 3),
        }
    content = metrics.get("cssContentSize") or metrics.get("contentSize") or {}
    width = max(1.0, float(content.get("width") or 1.0))
    height = max(1.0, float(content.get("height") or 1.0))
    capture_error: str | None = None
    png_bytes: int | None = None
    try:
        shot = connection.call(
            "Page.captureScreenshot",
            {
                "format": "png",
                # captureBeyondViewport re-renders the surface at the full document size,
                # which is what makes a full-page shot possible without scrolling and
                # stitching (stitching would leave seams and fixed-position artifacts).
                "captureBeyondViewport": True,
                "clip": {"x": 0, "y": 0, "width": width, "height": height, "scale": 1},
            },
            timeout=remaining(),
        )
        png_path.parent.mkdir(parents=True, exist_ok=True)
        png_path.write_bytes(base64.b64decode(shot["data"]))
        png_bytes = png_path.stat().st_size
    except (CdpError, KeyError) as screenshot_error:
        capture_error = f"screenshot failed: {screenshot_error}"

    final_status = 200
    final_url = probe["url"]
    if tracker.document_responses:
        # A redirect chain produces several Document responses; the last one is the
        # response that actually rendered.
        final_status = tracker.document_responses[-1]["status"] or 200

    # A page that redirects is compared as the page it redirected to, so say so in the
    # report. The failure this guards against is a login_required page captured signed
    # out: the entry would otherwise look like a normal capture of the requested path
    # while actually holding the sign-in page.
    requested_path = normalized_path(url)
    landed_path = normalized_path(final_url)
    if landed_path != requested_path:
        warnings.append(
            f"final URL path {landed_path} differs from the requested path {requested_path} "
            "(the page redirected; a sign-in redirect lands on the login page, not the page that was requested)"
        )

    return {
        "status": int(final_status),
        "url": final_url,
        "title": probe["title"],
        "stylesheets": probe["stylesheets"],
        "scroll_width": int(probe["scrollWidth"]),
        "scroll_height": int(probe["scrollHeight"]),
        "animated_elements": int(probe["animated"]),
        "masked": masked,
        "png_bytes": png_bytes,
        "warnings": warnings,
        "error": capture_error,
        "seconds": round(time.monotonic() - started, 3),
    }


# --------------------------------------------------------------------------
# capture
# --------------------------------------------------------------------------


def prepare_capture_dir(path: Path, *, force: bool) -> None:
    """Make the capture directory usable, refusing to delete a directory we did not write."""
    if path.exists():
        if (path / "manifest.json").exists() or not any(path.iterdir()) or force:
            shutil.rmtree(path)
        else:
            fail(f"{path} exists but is not a capture directory (no manifest.json). Pass --force to replace it anyway.")
    path.mkdir(parents=True, exist_ok=True)


def parse_base_overrides(values: list[str]) -> dict[str, str]:
    overrides: dict[str, str] = {}
    for raw in values:
        for pair in raw.split(","):
            pair = pair.strip()
            if not pair:
                continue
            name, separator, url = pair.partition("=")
            name, url = name.strip(), url.strip()
            if not separator or not name or not url.startswith(("http://", "https://")):
                fail(f"--base expects NAME=http://host:port entries, got {pair!r}")
            overrides[name] = url.rstrip("/")
    return overrides


def resolve_base_urls(overrides: dict[str, str], only: list[str]) -> dict[str, str]:
    for name in overrides:
        if name in EXCLUDED_VARIANTS:
            fail(f"variant {name!r} is excluded from this harness on purpose")
    excluded = sorted(set(only) & EXCLUDED_VARIANTS)
    if excluded:
        fail(f"variant {', '.join(excluded)} is excluded from this harness on purpose")
    bases = dict(DEFAULT_BASE_URLS)
    bases.update(overrides)
    if only:
        unknown = sorted(set(only) - set(bases))
        if unknown:
            fail(f"--only names unknown variants: {', '.join(unknown)}")
        bases = {name: url for name, url in bases.items() if name in set(only)}
    if not bases:
        fail("no variants selected")
    return bases


def directory_size(path: Path) -> int:
    return sum(entry.stat().st_size for entry in path.rglob("*") if entry.is_file())


def cmd_capture(args: argparse.Namespace) -> int:
    chrome = find_chrome(args.chrome)
    bases = resolve_base_urls(parse_base_overrides(args.base), list(args.only))
    pages_file = str(args.pages) if args.pages else None
    store = Path(args.out).expanduser().resolve() if args.out else (DEFAULT_STORE / args.label).expanduser().resolve()
    prepare_capture_dir(store, force=args.force)
    username, password = resolve_credentials(args)
    viewports = parse_viewports(list(args.viewport))

    started = time.monotonic()
    created = datetime.now(UTC).isoformat(timespec="seconds")
    print(f"### capture {args.label!r} -> {store}")
    print(f"    chrome {chrome}")
    print(f"    viewports: {', '.join(f'{name}={size[0]}x{size[1]}' for name, size in viewports.items())}")
    print(f"    variants: {', '.join(f'{name}={url}' for name, url in bases.items())}")
    if username:
        print(f"    login: {args.login_path} as {username!r}, verified against {args.require_login_path}")
    else:
        print("    login: none (gated pages will be captured as the login page)")
    if args.mask:
        print(f"    masks: {', '.join(args.mask)}")

    page_lists: dict[str, list[tuple[str, str]]] = {}
    discovery: dict[str, Any] = {}
    for variant, base_url in bases.items():
        pages, record = resolve_pages(base_url, pages_file)
        page_lists[variant] = pages
        discovery[variant] = record
        details = sum(1 for label, _ in pages if "-detail-" in label)
        print(f"    {variant:9} {len(pages)} pages ({details} discovered from listings) at {base_url}")
        for label, path in pages:
            print(f"      {label:24} {path}")
        for listing, listing_record in (record.get("listings") or {}).items():
            print(f"      discovery {listing}: status={listing_record['status']} matched={listing_record['matched']}")

    entries: list[dict[str, Any]] = []
    login_records: dict[str, dict[str, Any]] = {}
    aborted: set[str] = set()
    errors = 0
    with launch_chrome(chrome) as port:
        for variant, base_url in bases.items():
            pages = page_lists[variant]
            print(f"### {variant} ({base_url})")
            with open_variant_session(port) as connection:
                tracker = NetworkTracker()
                connection.add_listener(tracker.handle)
                login_record: dict[str, Any] = {
                    "used": False,
                    "username": None,
                    "status": None,
                    "final_url": None,
                    "verified": None,
                    "login_path": args.login_path,
                    "require_login_path": args.require_login_path,
                    "login_status": None,
                    "login_final_url": None,
                    "fields": None,
                    "error": None,
                }
                if username and password:
                    login_record = login_variant(
                        connection,
                        tracker,
                        base_url=base_url,
                        username=username,
                        password=password,
                        login_path=args.login_path,
                        require_login_path=args.require_login_path,
                        timeout=args.page_timeout,
                    )
                    if not login_record["verified"]:
                        # Never fall back to an anonymous capture once credentials were
                        # supplied: that is the silent comparison this harness must not make.
                        login_records[variant] = login_record
                        aborted.add(variant)
                        errors += 1
                        print(f"### {variant}: login FAILED, skipping every page of this variant")
                        print(f"    {login_record['error']}")
                        continue
                    print(
                        f"    login ok: {login_record['final_url']} "
                        f"(status {login_record['status']}), fields {login_record['fields']}"
                    )
                login_records[variant] = login_record
                for viewport, (width, height) in viewports.items():
                    connection.call(
                        "Emulation.setDeviceMetricsOverride",
                        {"width": width, "height": height, "deviceScaleFactor": 1, "mobile": False},
                    )
                    for label, path in pages:
                        relative_png = Path(variant) / viewport / f"{label}.png"
                        relative_styles = Path(variant) / viewport / f"{label}.styles.json"
                        result = capture_page(
                            connection,
                            tracker,
                            url=base_url + path,
                            png_path=store / relative_png,
                            styles_path=store / relative_styles,
                            masks=list(args.mask),
                            timeout=args.page_timeout,
                        )
                        entry: dict[str, Any] = {
                            "variant": variant,
                            "viewport": viewport,
                            "page": label,
                            "path": path,
                            "png": relative_png.as_posix(),
                            "styles": relative_styles.as_posix(),
                            **result,
                        }
                        entries.append(entry)
                        if result.get("error"):
                            errors += 1
                            print(f"  {variant:9} {viewport:7} {label:24} ERROR {result['error']}")
                        else:
                            print(
                                f"  {variant:9} {viewport:7} {label:24} {result['status']:>3} "
                                f"{result['png_bytes']:>8}B {result['seconds']:>6.2f}s "
                                f"{','.join(result['warnings']) or ''}"
                            )

    seconds = round(time.monotonic() - started, 3)
    # How many elements each --mask selector hid, so a selector that matched nothing (or
    # matched far fewer elements than expected) is visible in the report rather than
    # being assumed to have worked. The per-view count is in each page entry; this is the
    # run total, and a selector that matched nothing anywhere is warned about here once
    # instead of once per page (most pages legitimately contain neither masked element).
    mask_matches: dict[str, dict[str, int]] = {selector: {"views": 0, "elements": 0} for selector in args.mask}
    for entry in entries:
        for selector, count in (entry.get("masked") or {}).items():
            totals = mask_matches.setdefault(selector, {"views": 0, "elements": 0})
            if count:
                totals["views"] += 1
                totals["elements"] += count
    if args.mask:
        print("### masks")
        for selector, totals in mask_matches.items():
            note = "" if totals["elements"] else "  WARNING: matched no element in any captured view"
            print(f"    {selector!r}: {totals['elements']} elements in {totals['views']} views{note}")
    manifest = {
        "version": 2,
        "kind": "css-regression-capture",
        "properties": list(STYLE_PROPERTIES),
        "label": args.label,
        "created": created,
        "store": str(store),
        "chrome": chrome,
        "blocked_urls": list(UNSTABLE_URL_PATTERNS),
        "masks": list(args.mask),
        "mask_matches": mask_matches,
        "viewports": {name: list(size) for name, size in viewports.items()},
        "tree": tree_identity(),
        "variants": {
            name: {
                "base_url": url,
                "login": login_records.get(name),
                "aborted": name in aborted,
            }
            for name, url in bases.items()
        },
        "page_list": {
            name: [{"page": label, "path": path} for label, path in pages] for name, pages in page_lists.items()
        },
        "discovery": discovery,
        "pages": entries,
        "counts": {
            "variants": len(bases),
            "views": len(entries),
            "errors": errors,
        },
        "seconds": seconds,
        "bytes": directory_size(store),
    }
    (store / "manifest.json").write_text(json.dumps(manifest, indent=1) + "\n", encoding="utf-8")
    print(
        f"### {len(entries)} views, {errors} errors, {seconds:.1f}s, "
        f"{manifest['bytes'] / (1024 * 1024):.1f} MiB -> {store / 'manifest.json'}"
    )
    return 1 if errors else 0


# --------------------------------------------------------------------------
# compare
# --------------------------------------------------------------------------


def parse_viewports(values: list[str]) -> dict[str, tuple[int, int]]:
    """Return the viewport set to capture, defaulting to VIEWPORTS.

    `--viewport name=WIDTHxHEIGHT` replaces the default set, so a thorough run can add
    the widths between the two defaults without changing what a routine run costs.
    """
    if not values:
        return dict(VIEWPORTS)
    viewports: dict[str, tuple[int, int]] = {}
    for value in values:
        name, _, size = value.partition("=")
        width, _, height = size.lower().partition("x")
        if not name or not width.isdigit() or not height.isdigit():
            fail(f"--viewport expects NAME=WIDTHxHEIGHT, got {value!r}")
        viewports[name] = (int(width), int(height))
    return viewports


def tree_identity() -> dict[str, Any]:
    """Identify the working tree a capture was taken from.

    A capture pair from the same tree proves determinism, not parity, and the two are
    indistinguishable afterwards without this. The git commit plus the dirty flag is
    enough to tell them apart, and it is cheap; a tree outside git records empty
    fields and comparisons then simply cannot make the same-tree claim.
    """

    def git(*arguments: str) -> str:
        try:
            completed = subprocess.run(
                ["git", *arguments],
                capture_output=True,
                text=True,
                timeout=15,
                check=False,
            )
        except OSError, subprocess.SubprocessError:
            return ""
        return completed.stdout.strip() if completed.returncode == 0 else ""

    head = git("rev-parse", "HEAD")
    status = git("status", "--porcelain")
    return {
        "head": head,
        "dirty": bool(status) if head else None,
        "dirty_files": len(status.splitlines()) if head else None,
    }


def load_manifest(directory: Path) -> dict[str, Any]:
    path = directory / "manifest.json"
    if not path.exists():
        fail(f"{directory} has no manifest.json, so it is not a capture directory")
    manifest: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    if manifest.get("kind") != "css-regression-capture":
        fail(f"{path} is not a capture manifest (kind={manifest.get('kind')!r})")
    return manifest


def compatibility_refusal(before: dict[str, Any], after: dict[str, Any]) -> str | None:
    """Describe why two captures cannot be compared, or None when they can."""
    if before.get("version") != after.get("version"):
        return f"capture format version differs: {before.get('version')} vs {after.get('version')}"
    if before.get("properties") != after.get("properties"):
        before_props = set(before.get("properties") or [])
        after_props = set(after.get("properties") or [])
        return (
            "the captures probed different properties "
            f"(+{len(after_props - before_props)} only in after, -{len(before_props - after_props)} only in before); "
            "recapture both sides with one harness version"
        )
    if before["viewports"] != after["viewports"]:
        return f"viewports differ: {before['viewports']} vs {after['viewports']}"
    for label, manifest in (("before", before), ("after", after)):
        viewport_count = len(manifest.get("viewports") or {})
        recorded: dict[str, int] = {}
        for entry in manifest["pages"]:
            recorded[entry["variant"]] = recorded.get(entry["variant"], 0) + 1
        for variant, page_list in (manifest.get("page_list") or {}).items():
            expected = len(page_list) * viewport_count
            seen = recorded.get(variant, 0)
            if seen != expected:
                return (
                    f"the {label} capture holds {seen} of {expected} views for {variant} "
                    f"({len(page_list)} pages x {viewport_count} viewports). A variant whose "
                    "sign-in failed is dropped from both sides, so comparing would silently "
                    "accept a capture with no pages for it"
                )
    before_pages = {(p["variant"], p["viewport"], p["page"]) for p in before["pages"]}
    after_pages = {(p["variant"], p["viewport"], p["page"]) for p in after["pages"]}
    only_before = sorted(f"{v}/{vp}/{page}" for v, vp, page in before_pages - after_pages)
    only_after = sorted(f"{v}/{vp}/{page}" for v, vp, page in after_pages - before_pages)
    if only_before or only_after:
        parts = []
        if only_before:
            parts.append(f"only in before: {', '.join(only_before[:6])}")
        if only_after:
            parts.append(f"only in after: {', '.join(only_after[:6])}")
        return "resolved page sets differ (" + "; ".join(parts) + ")"
    before_paths = {(p["variant"], p["viewport"], p["page"]): p["path"] for p in before["pages"]}
    after_paths = {(p["variant"], p["viewport"], p["page"]): p["path"] for p in after["pages"]}
    moved = sorted(key for key in before_paths if before_paths[key] != after_paths.get(key))
    if moved:
        sample = ", ".join(
            f"{v}/{vp}/{page}: {before_paths[(v, vp, page)]} -> {after_paths[(v, vp, page)]}"
            for v, vp, page in moved[:4]
        )
        return f"{len(moved)} pages resolved to a different path ({sample})"
    return None


def any_channel_mask(difference: Image.Image) -> Image.Image:
    """A mask of pixels where any channel differs at all.

    A luminance conversion would miss a difference that only moves a single channel
    slightly (a 1/255 blue shift is invisible to Rec. 601 weights), so the bands are
    thresholded separately and combined.
    """
    bands = difference.split()
    mask = bands[0].point(lambda value: 255 if value else 0)
    for band in bands[1:]:
        mask = ImageChops.lighter(mask, band.point(lambda value: 255 if value else 0))
    return mask


def pixel_difference(before_png: Path, after_png: Path, diff_path: Path | None) -> dict[str, Any]:
    """Compare two PNGs. A size change counts as changed even where the overlap matches."""
    with Image.open(before_png) as handle:
        before = handle.convert("RGB")
    with Image.open(after_png) as handle:
        after = handle.convert("RGB")
    size_mismatch = before.size != after.size
    overlap_w = min(before.width, after.width)
    overlap_h = min(before.height, after.height)
    left = before.crop((0, 0, overlap_w, overlap_h))
    right = after.crop((0, 0, overlap_w, overlap_h))
    difference = ImageChops.difference(left, right)
    mask = any_channel_mask(difference)
    changed = int(mask.histogram()[255])
    if size_mismatch:
        changed += before.width * before.height + after.width * after.height - 2 * overlap_w * overlap_h
    canvas = (max(before.width, after.width), max(before.height, after.height))
    percent = 100.0 * changed / (canvas[0] * canvas[1])
    bbox = mask.getbbox()
    if bbox is not None and size_mismatch:
        bbox = (0, 0, canvas[0], canvas[1])
    if bbox is not None and diff_path is not None:
        diff_path.parent.mkdir(parents=True, exist_ok=True)
        # Amplify the raw delta: a one-level channel shift is the usual regression and
        # is invisible in a plain difference image.
        difference.point(lambda value: min(255, value * DIFF_AMPLIFY)).save(diff_path)
    return {
        "differing_pixels": changed,
        "percent": round(percent, 6),
        "bbox": list(bbox) if bbox else None,
        "size_mismatch": size_mismatch,
        "before_size": list(before.size),
        "after_size": list(after.size),
    }


# Head elements that are never rendered on their own, so adding or removing one
# cannot shift layout: a stylesheet link, a meta tag, a script. A deliberate head
# edit shows up in these buckets and is reported, but it does not fail the gate.
# Anything else that appears or disappears is treated as a geometry change.
NON_RENDERED_HEAD_TAGS = frozenset({"link", "meta", "script", "style", "title", "base", "noscript"})


def is_non_rendered_head_element(key: str) -> bool:
    """True for an element key such as ``html>head:nth-of-type(1)>link:nth-of-type(4)``.

    Keys carry an ``nth-of-type`` suffix on every step, so the head segment is
    matched by its tag name rather than by equality with ``head``.
    """
    parts = key.split(">")
    if len(parts) < 3:
        return False
    if parts[1].split(":", 1)[0] != "head":
        return False
    return parts[-1].split(":", 1)[0] in NON_RENDERED_HEAD_TAGS


def style_difference(before_payload: dict[str, Any], after_payload: dict[str, Any]) -> dict[str, Any]:
    """Per element: added, removed, and each computed property that changed.

    Element additions and removals inside ``<head>`` are split into
    ``head_before_only`` and ``head_after_only``. Adding a stylesheet link or
    dropping a duplicate meta tag is a deliberate head edit, not a styling
    regression, and treating it as one made the gate unusable for any change to
    the shared shell.
    """
    before_elements = {element["k"]: element["s"] for element in before_payload["elements"]}
    after_elements = {element["k"]: element["s"] for element in after_payload["elements"]}
    gone = sorted(set(before_elements) - set(after_elements))
    added = sorted(set(after_elements) - set(before_elements))
    head_before_only = [key for key in gone if is_non_rendered_head_element(key)]
    head_after_only = [key for key in added if is_non_rendered_head_element(key)]
    head_keys = set(head_before_only) | set(head_after_only)
    before_only = [key for key in gone if key not in head_keys]
    after_only = [key for key in added if key not in head_keys]
    changed: list[dict[str, Any]] = []
    geometry = False
    for key in sorted(set(before_elements) & set(after_elements)):
        properties: dict[str, dict[str, Any]] = {}
        for name in STYLE_PROPERTIES:
            left = before_elements[key].get(name)
            right = after_elements[key].get(name)
            if left != right:
                properties[name] = {"before": left, "after": right}
        if properties:
            if not set(properties) <= COSMETIC_PROPERTIES:
                geometry = True
            changed.append({"key": key, "properties": properties})
    if before_only or after_only:
        geometry = True
    if before_only or after_only or changed:
        severity = "geometry" if geometry else "cosmetic"
    else:
        severity = "none"
    return {
        "before_only": before_only,
        "after_only": after_only,
        "head_before_only": head_before_only,
        "head_after_only": head_after_only,
        "changed": changed,
        "changed_properties": sum(len(entry["properties"]) for entry in changed),
        "severity": severity,
    }


def print_style_details(row: dict[str, Any], limit: int) -> None:
    style = row["style"]
    lines: list[str] = []
    if style["before_only"]:
        lines.append(
            f"    elements only in before ({len(style['before_only'])}): {', '.join(style['before_only'][:4])}"
        )
    if style["after_only"]:
        lines.append(f"    elements only in after ({len(style['after_only'])}): {', '.join(style['after_only'][:4])}")
    for label, keys in (
        ("non-rendered head elements only in before", style["head_before_only"]),
        ("non-rendered head elements only in after", style["head_after_only"]),
    ):
        if keys:
            lines.append(f"    {label} ({len(keys)}, informational, not a failure): {', '.join(keys[:4])}")
    for entry in style["changed"]:
        for name, values in entry["properties"].items():
            tag = "cosmetic" if name in COSMETIC_PROPERTIES else "geometry"
            lines.append(f"    {entry['key']}\n      {name} [{tag}]: {values['before']!r} -> {values['after']!r}")
            if len(lines) >= limit:
                break
        if len(lines) >= limit:
            break
    truncated = len(lines) >= limit and (style["changed_properties"] > limit or len(style["before_only"]) > 4)
    print("\n".join(lines))
    if truncated:
        print("    ... truncated, the full detail is in comparison.json")


def cmd_compare(args: argparse.Namespace) -> int:
    before_dir = Path(args.before).expanduser().resolve()
    after_dir = Path(args.after).expanduser().resolve()
    out = Path(args.out).expanduser().resolve() if args.out else after_dir
    out.mkdir(parents=True, exist_ok=True)
    before = load_manifest(before_dir)
    after = load_manifest(after_dir)

    print(f"before {before_dir}  (label {before['label']!r}, {before['created']})")
    print(f"after  {after_dir}  (label {after['label']!r}, {after['created']})")
    for name, info in after["variants"].items():
        other = (before["variants"].get(name) or {}).get("base_url")
        if other and other != info["base_url"]:
            print(f"note: {name} was captured at {other} before and {info['base_url']} after")

    # Content that follows the clock changes between two captures for reasons that are
    # not the stylesheet: the homepage calendar marks today, the event list filters on
    # whether an event has ended, and relative times are computed from the request time.
    # Say so when the pair is far enough apart for it to matter, because the symptoms
    # look exactly like a style regression.
    try:
        gap_minutes = (
            abs((datetime.fromisoformat(after["created"]) - datetime.fromisoformat(before["created"])).total_seconds())
            / 60
        )
    except KeyError, ValueError:
        gap_minutes = None
    if gap_minutes is not None and gap_minutes > 5:
        print(
            f"note: the captures are {gap_minutes:.0f} minutes apart. Pages whose content follows "
            "the clock can differ for that reason alone: the homepage calendar marks today (so a "
            "pair taken across local midnight always shows it), the homepage event list drops an "
            "event once it has ended, and relative sign-up times move"
        )

    same_tree = bool(before.get("tree")) and before.get("tree") == after.get("tree")
    if same_tree and not args.same_tree_ok:
        tree = before.get("tree") or {}
        reason = (
            "both captures come from the same working tree "
            f"(HEAD {str(tree.get('head'))[:12] or 'unknown'}, dirty files {tree.get('dirty_files')}); "
            "comparing a tree against itself proves determinism, not parity. "
            "Pass --same-tree-ok when that is what you mean to check"
        )
        print(f"\nrefusing to compare: {reason}")
        (out / "comparison.json").write_text(
            json.dumps(
                {
                    "kind": "css-regression-comparison",
                    "refused": True,
                    "reason": reason,
                    "same_tree": True,
                    "tree": before.get("tree"),
                    "before": str(before_dir),
                    "after": str(after_dir),
                },
                indent=1,
            )
            + "\n",
            encoding="utf-8",
        )
        return 2

    refusal = compatibility_refusal(before, after)
    if refusal:
        print(f"\nrefusing to compare: {refusal}")
        (out / "comparison.json").write_text(
            json.dumps(
                {
                    "kind": "css-regression-comparison",
                    "refused": True,
                    "reason": refusal,
                    "before": str(before_dir),
                    "after": str(after_dir),
                },
                indent=1,
            )
            + "\n",
            encoding="utf-8",
        )
        return 2

    before_index = {(p["variant"], p["viewport"], p["page"]): p for p in before["pages"]}
    rows: list[dict[str, Any]] = []
    for entry in after["pages"]:
        key = (entry["variant"], entry["viewport"], entry["page"])
        other = before_index[key]
        row: dict[str, Any] = {
            "variant": entry["variant"],
            "viewport": entry["viewport"],
            "page": entry["page"],
            "path": entry["path"],
            "status": {"before": other.get("status"), "after": entry.get("status")},
        }
        reasons: list[str] = []
        before_status = other.get("status")
        after_status = entry.get("status")
        if before_status != after_status:
            reasons.append(f"status {before_status} -> {after_status} (the page answered differently)")
        elif after_status is not None and after_status != 200:
            reasons.append(f"status {after_status} (not 200, so this view proves nothing)")
        before_png = before_dir / other["png"]
        after_png = after_dir / entry["png"]
        if entry.get("error") or other.get("error"):
            row["error"] = {"before": other.get("error"), "after": entry.get("error")}
            reasons.append("capture error")
            row["pixel"] = {"differing_pixels": None, "percent": None, "bbox": None, "size_mismatch": None}
        elif not before_png.exists() or not after_png.exists():
            # A file missing from a capture directory is a hard failure, not a
            # difference: nothing can be concluded about that view.
            missing = [path.as_posix() for path in (before_png, after_png) if not path.exists()]
            row["error"] = {"before": other.get("error"), "after": entry.get("error")}
            reasons.append(f"missing screenshot: {', '.join(missing)}")
            row["pixel"] = {"differing_pixels": None, "percent": None, "bbox": None, "size_mismatch": None}
        else:
            diff_name = Path("diffs") / f"{entry['variant']}__{entry['viewport']}__{entry['page']}.diff.png"
            diff_path = None if args.list_only else out / diff_name
            pixel = pixel_difference(before_png, after_png, diff_path)
            pixel["diff_png"] = diff_name.as_posix() if pixel["bbox"] else None
            pixel["exceeds_tolerance"] = (
                pixel["differing_pixels"] > args.tolerance or pixel["percent"] > args.max_percent
            )
            row["pixel"] = pixel
            if pixel["exceeds_tolerance"]:
                reasons.append(f"{pixel['differing_pixels']} differing pixels ({pixel['percent']:.4f}%)")
        before_styles_path = before_dir / other["styles"]
        after_styles_path = after_dir / entry["styles"]
        if before_styles_path.exists() and after_styles_path.exists():
            style = style_difference(
                json.loads(before_styles_path.read_text(encoding="utf-8")),
                json.loads(after_styles_path.read_text(encoding="utf-8")),
            )
        else:
            style = {
                "before_only": [],
                "after_only": [],
                "head_before_only": [],
                "head_after_only": [],
                "changed": [],
                "changed_properties": 0,
                "severity": "none",
                "missing": [path.as_posix() for path in (before_styles_path, after_styles_path) if not path.exists()],
            }
            reasons.append(f"missing style snapshot: {', '.join(style['missing'])}")
        row["style"] = style
        row["style_counts"] = {
            "before_only": len(style["before_only"]),
            "after_only": len(style["after_only"]),
            "changed_properties": style["changed_properties"],
            "head_before_only": len(style["head_before_only"]),
            "head_after_only": len(style["head_after_only"]),
        }
        style_failed = bool(style["before_only"] or style["after_only"] or style["changed"])
        if style_failed and not args.allow_style_changes:
            reasons.append(
                f"style: +{len(style['after_only'])} -{len(style['before_only'])} ~{style['changed_properties']}"
            )
        row["changed"] = bool(reasons)
        row["reasons"] = reasons
        rows.append(row)

    rows.sort(key=lambda row: (not row["changed"], row["variant"], row["viewport"], row["page"]))
    header = f"{'variant':9} {'viewport':8} {'page':24} {'st':>4} {'diff_px':>9} {'diff_%':>8} {'bbox':20} {'style':>14} {'severity':9}"
    print(f"\n{header}")
    print("-" * len(header))
    for row in rows:
        pixel = row["pixel"]
        diff_px = "-" if pixel.get("differing_pixels") is None else str(pixel["differing_pixels"])
        percent = "-" if pixel.get("percent") is None else f"{pixel['percent']:.4f}"
        bbox = "-" if not pixel.get("bbox") else ",".join(str(value) for value in pixel["bbox"])
        counts = row["style_counts"]
        style_note = f"+{counts['after_only']} -{counts['before_only']} ~{counts['changed_properties']}"
        status = row["status"]["after"] if row["status"]["after"] is not None else "-"
        print(
            f"{row['variant']:9} {row['viewport']:8} {row['page']:24} {status!s:>4} {diff_px:>9} {percent:>8} "
            f"{bbox:20} {style_note:>14} {row['style']['severity']:9}"
        )

    changed_rows = [row for row in rows if row["changed"]]
    if changed_rows:
        print("\ndifferences:")
        for row in changed_rows:
            detail = "; ".join(row["reasons"]) or "changed"
            print(f"  {row['variant']}/{row['viewport']}/{row['page']} ({row['path']}): {detail}")
            print_style_details(row, args.detail_lines)

    totals = {
        "views": len(rows),
        "changed_views": len(changed_rows),
        "differing_pixels": sum((row["pixel"].get("differing_pixels") or 0) for row in rows),
        "capture_errors": sum(1 for row in rows if "error" in row),
        "geometry_views": sum(1 for row in rows if row["style"]["severity"] == "geometry"),
        "cosmetic_only_views": sum(1 for row in rows if row["style"]["severity"] == "cosmetic"),
    }
    result = {
        "kind": "css-regression-comparison",
        "refused": False,
        "created": datetime.now(UTC).isoformat(timespec="seconds"),
        "before": str(before_dir),
        "after": str(after_dir),
        "labels": {"before": before["label"], "after": after["label"]},
        "viewports": after["viewports"],
        "tolerance": {
            "differing_pixels": args.tolerance,
            "max_percent": args.max_percent,
            "allow_style_changes": bool(args.allow_style_changes),
        },
        "ok": not changed_rows,
        "totals": totals,
        "pages": rows,
    }
    (out / "comparison.json").write_text(json.dumps(result, indent=1) + "\n", encoding="utf-8")

    print(
        f"\n{totals['views']} views compared, {totals['changed_views']} changed, "
        f"{totals['differing_pixels']} differing pixels, "
        f"{totals['geometry_views']} geometry/colour style diffs, "
        f"{totals['cosmetic_only_views']} cosmetic style diffs, "
        f"{totals['capture_errors']} capture errors"
    )
    print(f"tolerance: {args.tolerance} pixels, {args.max_percent}% per view")
    if changed_rows:
        print(
            f"verdict: FAILED, first offender {changed_rows[0]['variant']}/{changed_rows[0]['viewport']}/{changed_rows[0]['page']}"
        )
    else:
        print("verdict: IDENTICAL")
    print(f"report: {out / 'comparison.json'}")
    return 1 if changed_rows else 0


# --------------------------------------------------------------------------
# entry point
# --------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command", required=True)

    capture = sub.add_parser("capture", help="capture every page, viewport and variant")
    capture.add_argument("--label", required=True, help="name of this capture, used in the store path and reports")
    capture.add_argument(
        "--out",
        default=None,
        help=f"capture directory (default: {DEFAULT_STORE}/<label>)",
    )
    capture.add_argument(
        "--only",
        action="append",
        default=[],
        help="capture only this variant (repeatable), e.g. --only date",
    )
    capture.add_argument(
        "--base",
        action="append",
        default=[],
        help="override a variant base URL, e.g. --base date=http://127.0.0.1:8002,sf=http://127.0.0.1:8015",
    )
    capture.add_argument(
        "--pages",
        default=None,
        help="file with one path per line, replacing the seed list and detail discovery",
    )
    capture.add_argument(
        "--viewport",
        action="append",
        default=[],
        metavar="NAME=WIDTHxHEIGHT",
        help=(
            "viewport to capture, replacing the default set (repeatable, for example "
            "--viewport tablet=900x1000). Default: desktop=1600x1000 and mobile=390x844; "
            "everything between them is a breakpoint band nothing checks"
        ),
    )
    capture.add_argument(
        "--mask",
        action="append",
        default=[],
        metavar="CSS_SELECTOR",
        help=(
            "hide every element matching this CSS selector with visibility: hidden before the "
            "computed-style probe and the screenshot, for live content such as a clock "
            "(repeatable, for example --mask '#some-id')"
        ),
    )
    capture.add_argument(
        "--username",
        default=None,
        help=f"sign in before capturing (default: {USERNAME_ENV_VAR} if set); without it the capture is anonymous",
    )
    capture.add_argument(
        "--password",
        default=None,
        help=f"password for --username (default: {PASSWORD_ENV_VAR} if set); prefer the variable, a flag is visible in the process list",
    )
    capture.add_argument(
        "--login-path",
        default=DEFAULT_LOGIN_PATH,
        help=f"sign-in page to submit before capturing (default {DEFAULT_LOGIN_PATH})",
    )
    capture.add_argument(
        "--require-login-path",
        default=DEFAULT_REQUIRE_LOGIN_PATH,
        help=f"path that is only reachable when signed in, used to verify the session (default {DEFAULT_REQUIRE_LOGIN_PATH})",
    )
    capture.add_argument("--chrome", default=None, help="path to a Chromium binary")
    capture.add_argument(
        "--page-timeout",
        type=float,
        default=60.0,
        help="seconds allowed per page and viewport (default 60)",
    )
    capture.add_argument("--force", action="store_true", help="replace an existing non-capture directory")
    capture.set_defaults(func=cmd_capture)

    compare = sub.add_parser("compare", help="compare two captures and gate on the differences")
    compare.add_argument("--before", required=True, help="capture directory to compare from")
    compare.add_argument("--after", required=True, help="capture directory to compare against")
    compare.add_argument(
        "--out", default=None, help="where to write comparison.json and diffs (default: the after directory)"
    )
    compare.add_argument(
        "--tolerance",
        type=int,
        default=0,
        help="differing pixels permitted per view before it counts as changed (default 0)",
    )
    compare.add_argument(
        "--max-percent",
        type=float,
        default=0.0,
        help="differing pixel percentage permitted per view (default 0.0); a view fails when it exceeds either limit",
    )
    compare.add_argument(
        "--same-tree-ok",
        action="store_true",
        help=(
            "allow comparing two captures of the same working tree; that proves the "
            "harness is deterministic, not that a change left the page alone"
        ),
    )
    compare.add_argument(
        "--allow-style-changes",
        action="store_true",
        help="gate on pixels only, and report style differences without failing",
    )
    compare.add_argument(
        "--list-only",
        action="store_true",
        help="print the summary and the style counts, but write no diff images and no property dump",
    )
    compare.add_argument(
        "--detail-lines",
        type=int,
        default=40,
        help="style difference lines printed per view before truncation (default 40)",
    )
    compare.set_defaults(func=cmd_compare)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return int(args.func(args))
    except CdpError as error:
        # Per-page failures are recorded in the manifest; this catch is for a broken
        # browser session, which should read as a failure and not as a traceback.
        print(f"error: {error}", file=sys.stderr)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
