# Publications Development Notes

## Data Model (`publications/models.py`)
- `PDFFile` captures metadata, upload, and access flags. `slug` auto-fills from title if left blank and is guaranteed unique by `generate_unique_slug()`.
- `file` uses `PublicFileField`, which supports S3/alternative storage. When `USE_S3` is false, `delete()` removes the local file manually.
- `is_public` and `requires_login` are independent flags; a PDF can be hidden entirely or visible-but-gated.

## Admin (`publications/admin.py`)
- Custom `PDFFileAdmin` prepopulates slugs for new objects, exposes access controls, and locks the `file` field when editing to avoid accidental replacements.
- Fieldsets group metadata, access control, and timestamps for clarity.

## Views/URLs (`publications/views.py`)
- The app is installed for DaTe, KK, Biologica/biocum, and Pulterit. Each of those variants exposes the public list at `/publications/`.
- `pdf_list` paginates 12 items per page (sized to fit common 2/3/4/6-column grids) and filters by login status:
  - Anonymous users: `is_public=True` and `requires_login=False`.
  - Authenticated users: any `is_public=True` file (even if `requires_login=True`).
- The view also passes a `page_range` list built by `_compact_page_range()`; entries are page numbers or `None` (= ellipsis). The template uses this to render numbered page buttons with first/last/window pages and ellipsis gaps.
- `pdf_view` enforces the same checks and redirects unauthenticated users to `login` if necessary. Non-public files always return HTTP 403.

## Templates
- `publications/list.html` expects `page_obj` and `page_range`. Cards render PDF cover thumbnails client-side via PDF.js (see `static/common/publications/js/list.js`), so the template surfaces `pdf.get_file_url` to JS via a `data-pdf-url` attribute on each card.
- The list thumbnail renderer is intentionally lazy and capped at two concurrent PDF.js tasks. It avoids storing derivative images today, but larger libraries should prefer generated thumbnail files or browser/server-side cache headers so returning visitors do not re-fetch and re-render every cover.
- `publications/viewer.html` embeds the PDF via `pdf_url`. The viewer JS modules under `static/common/publications/js/` implement page transitions, swipe gestures, fullscreen, neighbor preloading and a reading-progress bar.
- Page-change animation is mode-dependent: two-page (desktop) uses a 3D book-flip rotation (`runTwoPageFlip` / `.page-flipper`), single-page (mobile) uses a card-shuffle horizontal slide (`runSinglePageShuffle` / `.page-shuffle`). The rotation reads as "turning a stiff page" which clashes with the touch-swipe gesture on mobile, where a slide matches the user's input direction.
- Two-page mode treats the first page as a cover (alone on the right) and, for PDFs with an even page count > 2, the last page as a back cover (alone on the left). PDFs with an odd page count don't get a back-cover view — the final spread `(N-1, N)` already shows the last page. 2-page PDFs render as a single `(1, 2)` spread and 1-page PDFs render the single page centered (no cover / back-cover concept applies). `spreadLayout.js` owns the shared spread rules, snaps page-jump / End-key targets to valid spread positions, and drives next/previous navigation plus nav-button state.
- Zoom: `state.scale` is a multiplier on top of a per-render **fit-to-viewport** baseline (`computeFitScale` in `pageRenderer.js`), so `scale=1` always fits the viewer width regardless of viewport size and `scale=2` is twice the fit. The .pdf-stage uses `overflow: auto` so zoomed pages that exceed the stage can be scrolled / panned, and `.page-canvas` no longer caps to `max-width: 100%` (which previously made the user-visible zoom a no-op). The viewer also re-renders on window resize so the fit baseline keeps tracking the viewport.

## Theming
- `publications.css` (viewer) and `list.css` declare a small semantic palette scoped to `.pdf-shell` / `.publications-page` (`--pub-surface`, `--pub-surface-pill`, `--pub-surface-hover`, `--pub-accent`, `--pub-accent-hover`, `--pub-accent-contrast`, `--pub-accent-soft`). New rules in this app should use those instead of reaching for `--primaryColor*` / `--linkColor*` directly.
- The surfaces map to the three `--primaryColorLight*` shades, which are consistently ordered dark→mid→lighter across every association. `--primaryColor` is intentionally avoided because its lightness relative to the others differs by association (pulterit's is bright gray).
- `--pub-accent` falls back `--accentColorBright` → `--linkColorLight` → `--linkColor` → `--secondaryColor`. Pulterit defines `--accentColorBright` (its pink) so it wins there; date and kk use their `--linkColorLight` (bright green); biocum (no `--linkColorLight`) falls through to `--linkColor`.
- The list view has a separate card sub-palette (`--pub-card-bg`, `--pub-card-fg`, `--pub-card-fg-soft`, `--pub-card-thumb-bg`, `--pub-card-thumb-shimmer`). It defaults to a **light card** (white bg, black text). Only DaTe opts into a dark card by defining `--pubCardBg` etc. in its `static/date/date/css/date-root.css`. A new association inherits the light theme automatically.
- The list heading uses `--pubListHeadingFg` when an association needs explicit contrast. Biologica sets it to white on the dark green page background, while Pulterit sets it to black on its light page background.
- The viewer chrome (toolbar, stage, loading, fullscreen, pagination, error) is dark-themed by default. An association can opt into a **light viewer** by defining `--pubChromeBg`, `--pubChromePill`, `--pubChromeHover`, `--pubStageBg`, `--pubChromeFg`, `--pubChromeFgSoft` in its `date-root.css`. Only pulterit does so, because the rest of pulterit's site is light-themed with pink accents.

## Extending
- For download tracking, introduce a `PDFDownload` model and increment in `pdf_view` before rendering.
- To support categories/tags, relate `PDFFile` to a taxonomy model and extend filters inside `pdf_list`.
- Consider caching `pdf_list` output if the library grows large; current implementation hits the database on every request.
