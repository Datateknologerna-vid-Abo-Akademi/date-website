# Publications Development Notes

## Data Model (`publications/models.py`)
- `PublicationCollection` groups publications under an admin-managed URL such as `/publications/publications/` or `/publications/ao/`. Collections own the primary visibility/access rule and can be public, login-only, membership-type-only, password-protected, or hidden. `cover_image` is shown on the collection index when present.
- `PDFFile` captures metadata, upload, redirect target, and secondary access flags. `slug` auto-fills from title if left blank and is guaranteed unique by `generate_unique_slug()`.
- `file` uses `PublicFileField`, which supports S3/alternative storage. When `USE_S3` is false, `delete()` removes the local file manually.
- `redirect_url` lets a publication point to an external reader instead of the internal PDF viewer. List cards still link to the internal detail URL so collection and PDF access checks run before the visitor is redirected.
- Entries must have either `file` or `redirect_url`; redirect-only entries can use `cover_image` for the list thumbnail.
- `is_public` and `requires_login` remain per-publication secondary flags. A PDF can be hidden inside an otherwise visible collection or require login in addition to the collection rule.
- Migration `0004` creates a default `Publications` collection with slug `publications` and assigns existing PDF rows to it.

## Admin (`publications/admin.py`)
- `PublicationCollectionAdmin` is the primary management surface. It lets admins create and reorder collections, set visibility, choose allowed membership types, and set/clear a password without storing plaintext. The change form also includes an inline table for the collection's publications so editors can manage collection access and publication-level flags in one place. The global PDF list is available through an **All PDF publications** tool link rather than a separate sidebar entry.
- The collection admin validates access combinations: password-protected collections must have a password, and selected-membership collections must select at least one membership type.
- Custom `PDFFileAdmin` prepopulates slugs for new objects, exposes collection/access columns, links back to the parent collection access settings, and locks the `file` field when editing to avoid accidental replacements. The PDF form shows a selected-collection access summary; `static/common/publications/js/admin-collection-access.js` refreshes that summary when the collection dropdown changes.
- Fieldsets group metadata, collection access, per-publication access control, and timestamps for clarity. The PDF changelist includes a shortcut back to collection/access management for editors who start from the publication list.

## Views/URLs (`publications/views.py`)
- The app is installed for DaTe, KK, Biologica/biocum, and Pulterit. Each of those variants exposes the public list at `/publications/`.
- `pdf_list` now renders a collection index. Hidden collections, empty collections, and collections unavailable to the current user are not listed.
- `collection_detail` renders `/publications/<collection-slug>/`, enforces collection access first, then paginates 12 items per page (sized to fit common 2/3/4/6-column grids) and filters by per-PDF login status:
  - Anonymous users: `is_public=True` and `requires_login=False`.
  - Authenticated users: any `is_public=True` file (even if `requires_login=True`).
- The view also passes a `page_range` list built by `_compact_page_range()`; entries are page numbers or `None` (= ellipsis). The template uses this to render numbered page buttons with first/last/window pages and ellipsis gaps.
- `pdf_view` serves `/publications/<collection-slug>/<publication-slug>/`. It enforces collection access first, then the per-publication checks, and only then redirects to `redirect_url` or renders the internal viewer.
- Legacy one-segment publication URLs (`/publications/<publication-slug>/`) are handled by `collection_detail` as a compatibility path. If the slug is not a collection but matches a publication, the same access checks run before a permanent redirect to the canonical collection URL.
- Collection access intentionally raises 404 for hidden collections and membership mismatches so unauthorized users cannot discover the collection or linked external URL from a direct request. Login-required collections redirect anonymous visitors to `settings.LOGIN_URL`; password-protected collections show a password form.

## Templates
- `publications/index.html` expects `collections` and renders the collection index, using `collection.cover_url` when available and falling back to an icon otherwise.
- `publications/list.html` expects `collection`, `page_obj`, and `page_range`. Cards link to `pdf.get_absolute_url`, even for external redirects. If `cover_image` is present it renders directly as the card thumbnail; otherwise PDF-backed cards render cover thumbnails client-side via PDF.js (see `static/common/publications/js/list.js`), so the template surfaces `pdf.get_file_url` to JS via a `data-pdf-url` attribute only when needed.
- `publications/password.html` renders the collection password prompt and posts back to the requested collection/publication URL.
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
- To support tags within a collection, relate `PDFFile` to a taxonomy model and extend filters inside `collection_detail`.
- Consider caching collection list output if the library grows large; current implementation hits the database on every request.
