# Shared CSS & Association Overrides

Every page is styled by hand-written stylesheets that the templates link
directly. There is no CSS build step, no preprocessor and no bundler, so the
files under `static/` are what the browser receives. This guide is the contract
for that system: where a sheet lives, which copy wins, what belongs in a
variant's palette, and the policies for load order, `!important`, breakpoints,
`z-index` and JavaScript hooks.

The tree holds 87 hand-written stylesheets (89 `.css` files minus the two
vendored minified bundles, `static/common/date/css/vanilla-calendar.min.css` and
`static/common/core/css/flatpickr.min.css`). A handful of them are linked by
`templates/common/core/base.html` and therefore load on every page; the rest are
linked by the pages that need them.

## Where stylesheets live and which copy wins

Shared sheets live at `static/common/<app>/css/<sheet>.css`. An association
override lives at `static/<assoc>/<app>/css/<sheet>.css`. `build_static_dirs`
in `core/settings/common.py` builds `STATICFILES_DIRS` with the association
directory first and `static/common` last, so Django's static finders resolve the
association path before the shared one.

A file at the same logical path **replaces** the shared file. It does not extend
it and it does not merge with it: if `static/kk/events/css/style.css` exists, no
rule from `static/common/events/css/style.css` is loaded for `kk`.

Static directories do **not** inherit parent variants, even where templates do.
`biocum`, `impuls` and `sf` pass `parent_variants=('date',)` to
`build_templates` and therefore fall back to `templates/date`, but each calls
`build_static_dirs('biocum' | 'impuls' | 'sf')` with no parents. A missing file
under `static/biocum/` falls through to `static/common/`, never to
`static/date/`.

The shipped variants are `date`, `kk`, `biocum`, `pulterit`, `sf` and `impuls`.
`demo` still exists in the tree (`core/settings/demo.py`, `static/demo/`) but is
slated for deletion: the per-association guard rules cover only the six shipped
variants, and the regression harness skips `demo`. The whole-tree ratchets
(`!important`, `z-index`, breakpoints, empty linked sheets) still scan its three
stylesheets, because a ratchet never fails when a file disappears. A shared
palette token rename does have to reach `demo`, because
`static/common/events/css/arsfest.css` consumes the token:
`--primaryColorMid` was renamed in `static/demo/date/css/date-root.css` and
`static/demo/core/css/base.css` for that reason, and no other `demo` file was
touched.

Across the six shipped variants, 24 association stylesheets currently sit at a
logical path that also exists under `static/common/`. Every one of those is a
shadow, and each one has to be justified by the rules in the section below on
the two legitimate ways to vary an association.

A few older sheets predate the `<app>/css/` layout:
`static/common/members/style.css`, `static/common/prettyjson/prettyjson.css`
and `static/common/css/admin_translation_tabs.css`. New sheets should use
`<app>/css/<sheet>.css`.

## Element selectors reach every page

Because the base sheets load on every page of the association, a selector that
matches a bare HTML element reaches parts of the page it was not written for.
The header sheets are the trap: the header is `<nav class="navbar ...">` in
`templates/common/core/header.html`, but pagination widgets are `<nav>` elements
too. django-tables2's table pagination renders a `<nav aria-label="Table
navigation">` on the archive documents and exam pages, the archive grid has
`nav#gallery-pagination-fallback`, and the publications list has
`nav.publications-pagination`. A rule written as
`nav { ... }` to style the header also painted a table pagination bar with the
header background, which on associations whose link colour matched their
background made the page numbers effectively invisible.

Rules to follow:

- Scope header rules to the header nav, for example `nav.navbar { ... }`. The
  same applies to rules that hide the chrome for a full page takeover, such as
  `nav.navbar, footer { display: none !important; }` on the Lucia and April
  pages.
- Keep table pagination styling under django-tables2's `.table-container`
  wrapper, which is what `static/common/core/css/pagination.css` does, so the
  news, publications and gallery paginations keep their own styling.
- Link the pagination sheet from every site shell. All six shipped shells now
  extend `templates/common/core/base.html`, which links it, so a new shell should
  extend the shared shell rather than copy it.

`core/tests/test_static_css.py` enforces the selector rules: it fails on any
unscoped `nav` selector under `static/` (a `nav` type selector must be
qualified immediately by a class, id or attribute, because an ancestor alone
such as `.content nav` can still contain a pagination nav) and on a rule in
`static/common/core/css/pagination.css` that escapes django-tables2's
`.table-container` wrapper. The shell itself is guarded separately:
`date/tests.py` renders `core/base.html` for every association and asserts that
the shared pagination sheet and the Font Awesome compatibility sheet are linked
(`test_every_association_shell_loads_the_shared_pagination_css` and
`test_every_association_shell_loads_font_awesome_compatibility_css`).

## The two legitimate ways to vary an association

An association has exactly two ways to differ visually from the shared look:

1. Delete the shadow, so the association uses the shared sheet unchanged.
2. Keep a small, genuine delta: a handful of rules that the shared sheet cannot
   express and that are specific to that association (a seasonal campaign, a
   layout the association does not share, and so on).

Copying a shared sheet into an association directory and editing a few lines is
what produced today's drift: it freezes a private fork of the shared rules, so
later fixes to `static/common/` never reach that association. Do not do it. A
guard test rejects a new shadow that is byte-identical to the shared file it
replaces. Three such copies existed when the rule landed
(`static/biocum/archive/css/document.css`, `static/biocum/core/css/ckeditor.css`
and `static/biocum/core/css/error-view.css`) and have been deleted, so the list
of accepted byte-identical shadows is now empty.

Where a variation is only a colour or another token, do not fork the rule: put
the value in the association's palette (next section) and let the shared sheet
consume the token.

## Palettes and tokens

Each association's palette is `static/<assoc>/date/css/date-root.css`, a
`:root` block of custom properties. `templates/common/core/base.html` links
`date/css/date-root.css`, which the static finders resolve to the association's
copy, so that file is the association's theming axis. Changing a palette value
re-themes every shared sheet that consumes it.

Naming convention for **new** tokens: kebab-case,
`--<family>-<role>[-<state>]`, for example `--pub-card-bg` (defined in
`static/common/publications/css/list.css`). The existing camelCase palette
(`--primaryColor`, `--linkColorLight`, and the rest of `date-root.css`) predates
the convention and is not being renamed wholesale, so expect both styles to
coexist. New tokens are kebab-case regardless.

Build semantic tokens from palette tokens rather than repeating a literal, and
give the palette token a fallback so the shared sheet still works for an
association that does not define it:

```css
--pub-card-bg: var(--pubCardBg, var(--secondaryColor));
```

A custom property consumed by a shared sheet must be defined either in every
association that loads that sheet or at the use site in a `var()` fallback. An
undefined `var()` with no fallback silently drops the declaration, so the rule
disappears with no console error and no test failure from the browser side; a
guard test catches the missing definition per association, and fails both when a
new gap appears and when a fixed gap is left in its frozen list.

Two classes of gap have been found and closed. `--linkColorLight`,
`--linkColorLightHover`, `--warning-darker` and `--textColorMedium` were not
declared for `biocum` although shared sheets consume them without a fallback
(`static/common/archive/css/detailed.css`, `static/common/news/css/style.css`,
`static/common/events/css/form.css`,
`static/common/members/css/two-factor.css`,
`static/common/members/css/functionary.css`); they are now defined in
`static/biocum/date/css/date-root.css`, aliased to biocum's own link tokens
where the meaning matched. Separately, `--silver`, `--lightSilver2` and
`--darkSilver2` were declared nowhere after the shared sheet that held them was
removed, which silently dropped `--mainArsfestColor`, `--mainArsfestTextColor`
and `--mainArsfestButtonHoverColor` in `static/date/events/css/arsfest.css` and
`static/pulterit/events/css/arsfest.css`; those three are restored locally in
both sheets until they are consolidated onto the shared arsfest sheet.

One accepted entry remains in the guard's frozen list:
`--luciaBackgroundColor` is referenced by `static/common/lucia/css/style.css`,
which only `kk` declares, because the `lucia` app is installed for `kk` alone.
The sheet is never linked on the other five associations, so the reference is
inert rather than broken, and it stays listed so the scanner does not have to
model which apps a variant installs.

## Load order, and why it is pinned

`templates/common/core/base.html` emits assets in a fixed order:

1. The project base sheets: `core/css/base.css`, `date/css/date-root.css`,
   `core/css/cookie-banner.css`, `core/css/pagination.css`.
2. The CDN vendor sheets: Bootstrap 5.1.3, bootstrap-icons, Line Awesome, then
   jQuery.
3. `{% block extra_head %}`.
4. `core/css/header.css`.
5. `{% block extra_header_css %}`.
6. `core/css/footer.css`.

The consequence that keeps coming back is step 1 versus step 2: because the
project base sheets load **before** Bootstrap, a project rule that ties on
specificity with a Bootstrap rule loses. That is why the tree contains
`!important` and over-qualified selectors such as `html body { ... }` and
`div a { ... }` in `static/<assoc>/core/css/base.css`. Treat this as a known,
deliberate constraint rather than a bug: reordering the two groups would change
rendering across all six associations at once, so it is not a local cleanup.

Page-level stylesheets belong in the `extra_head` or `extra_header_css` blocks.
A sheet that must win by order rather than by specificity goes in
`{% block extra_css %}`, which is the last stylesheet position in `<head>`, after
`core/css/footer.css`. A stylesheet that must beat a vendor sheet that loads
later has to be linked after that sheet. The vanilla-calendar bundle
(`static/common/date/css/vanilla-calendar.min.css`) is an example: the base
sheets and Bootstrap are already on the page before it is linked, so only a
later link can override its calendar rules.

## The `!important` policy

`!important` is permitted only to:

- beat a Bootstrap utility class that is itself `!important`;
- beat an inline style written by JavaScript;
- beat a third-party sheet that loads later.

Each use should carry a one-line comment naming the reason, as the
`keep img ratio correct` notes next to `width: auto !important` do. Many of the
existing uses have no such comment, so treating that as the standard is
aspirational: the comment is the rule for new work, and the uncommented
existing uses are debt.

The tree has 361 `!important` declarations across 37 hand-written stylesheets
(comment text excluded); the largest concentrations are 41 in each of
`static/biocum/events/css/arsfest.css`, `static/date/events/css/arsfest.css` and
`static/pulterit/events/css/arsfest.css`.
A guard test ratchets the per-file count, so a file's count can only go down:
adding a new `!important` to a file that is at its frozen count fails until one
is removed.

## Breakpoints

The intended scale is Bootstrap's, because Bootstrap 5.1.3 is the framework the
project is written against:

| Breakpoint | Mobile-first (`min-width`) | Desktop-first (`max-width`) |
|---|---|---|
| 576px | `min-width: 576px` | `max-width: 575.98px` |
| 768px | `min-width: 768px` | `max-width: 767.98px` |
| 992px | `min-width: 992px` | `max-width: 991.98px` |
| 1200px | `min-width: 1200px` | `max-width: 1199.98px` |
| 1400px | `min-width: 1400px` | `max-width: 1399.98px` |

Prefer mobile-first `min-width: Npx`, and use `max-width: (N - 0.02)px` when a
desktop-first rule is genuinely needed.

The tree does not follow this today. It contains 33 distinct media query
strings as written, including whitespace variants such as `(max-width : 992px)`
and `(min-width : 992px)`, prefixed variants such as `only screen and
(max-width: 900px)`, and near-duplicates such as `767px`, `767.98px` and
`768px`. A guard test normalises whitespace only, so it freezes 31 keys and
treats `(max-width : 992px)` as a repeat of `(max-width: 992px)`. Adding any
other query is a reviewed change that regenerates the baseline, and the query
must use the documented scale; the existing oddities are debt rather than
precedent.

## z-index

There is no scale today. The tree declares 15 distinct `z-index` values: 14
numbers from `-150` up to `1000000`, plus `inherit`. The mixing has visible
consequences:

- The archive lightbox controls (`#lightbox-dl-btn`, `#lightbox-share-btn`,
  `#lightbox-share-feedback`, `#lightbox-counter`) all sit at `1000000` in
  `static/common/archive/css/detailed.css`, one above the `999999` that the
  glightbox 3.3.1 bundle (loaded from jsDelivr by
  `templates/common/archive/partials/detail_scripts.html`) uses for its own
  container. The controls win only because the number happens to be larger, and
  all four share one value, so their internal order is not expressible.
- The cookie banner sits at `1000` in `static/common/core/css/cookie-banner.css`,
  below the Lucia snowflakes at `9999` in `static/common/lucia/css/style.css`.

The intended scale for new work:

| Layer | Value |
|---|---|
| Background and decorative layers | negative |
| Local stacking inside one component | 1 to 10 |
| Sticky chrome (header nav, offcanvas) | 100 |
| Page-level banner (cookie banner) | 1000 |
| Modal, lightbox and its controls | 9000 and above |

Within the modal and lightbox band, give each layer its own slot rather than
sharing one value: for example `9000` for a modal overlay, `9100` for the
lightbox container, and `9200`, `9210`, `9220` (and so on) for individual
controls. Distinct slots let a later rule order controls against each other,
which one shared `1000000` cannot. A guard test freezes each file's current
values and fails on any value that file did not already use, so converting a
file to the scale is a reviewed change that regenerates the baseline.

## JavaScript hooks

Styling classes must not be the contract with JavaScript. Renaming a class for
styling reasons silently breaks the behaviour that reads it, with no error
anywhere: neither the CSS nor the JavaScript complains.

Components should read `data-*` attributes. That is the established good pattern
in the archive gallery, where the server writes configuration onto
`#gallery-config` and `static/common/archive/js/detail-gallery.js` reads it
through `galleryConfig.dataset.*`, and in the event tab navigation, where each
tab carries `data-nav="..."` and the inline script in
`templates/common/events/arsfest_base.html` calls
`showPanel(element.dataset.nav)`.

Where a class is unavoidably a hook because the markup comes from a third-party
package or a legacy template, prefix it `js-`. No `js-` prefixed hook exists in
the tree yet.

These components still hook onto styling classes or ids and are the conversion
backlog:

- The archive lightbox (`static/common/archive/js/detail-gallery.js`) reads
  `.grid-item`, `.gallery-image`, `.gclose`, `.gnext` and `.goverlay`, alongside
  the `data-global-index` attribute it already uses.
- The publications viewer (`static/common/publications/js/pdfViewer.js`,
  `static/common/publications/js/main.js`) reads `#pdf-viewer` and `#pdf-shell`,
  and the publications list (`static/common/publications/js/list.js`) reads
  `.publication-thumb-canvas` and `.publication-card[data-pdf-url]`.
- The upload widget (`static/common/uploads/js/upload-init.js`) reads
  `.django-uppy-status` and `.django-uppy-remove` next to its `data-uppy-*`
  attributes.
- The `sf` logo animation (`static/sf/date/js/header-logo-animation.js`) reads
  `.hero-text-box .albin`.
- The admin translation tabs (`static/common/js/admin_translation_tabs.js`)
  reads `.mt`, the `mt-field-<language>` class prefix and
  `.translation-language-tabs`.

The most fragile of these is the `sf` logo animation. The guard near the top of
`static/sf/date/js/header-logo-animation.js` is
`if (!svg || !paths.length) return;`, so when the `.hero-text-box .albin`
selector misses (markup renamed, the block wrapped differently, the SVG split
into another partial) the whole animation silently does nothing. There is no
error, no warning and no test that notices. Convert this one to a `data-*` hook
before touching the `sf` header markup.

## Accessibility rules

Two rules are cheap to get right and easy to break:

- Never write `outline: none` (or `outline: 0`) without a `:focus-visible`
  replacement for the same element. Correct examples in the tree include
  `.publication-card:focus-visible` in `static/common/publications/css/list.css`,
  `.grid-item:focus-visible` and `.pagination a:focus-visible` in
  `static/common/archive/css/detailed.css`, and
  `.translation-language-tabs button:focus-visible` in
  `static/common/css/admin_translation_tabs.css`.
- Never signal state with colour alone. Give the state a second channel, as the
  admin translation tabs do by combining the `.active` class with
  `aria-pressed`.

No exceptions are documented. The hand-written stylesheets still contain 18
`outline: none` or `outline: 0` declarations against 9 `:focus-visible` rules,
so several elements lose their focus ring with nothing put back. That is debt,
not a licence: a change that adds `outline: none` must add the replacement.
`static/common/core/css/focus.css` is the shared replacement for the case that
mattered most, `.theme-button`: it draws a ring from the palette accent for
`:focus-visible` only, so mouse users see no change, and the variant
`static/<assoc>/core/css/base.css` sheets no longer switch the ring off.

## How to verify a change

Appearance parity is proven with `scripts/css_regression.py`, which captures a
full-page screenshot and a computed-style snapshot per page and viewport, then
compares two captures:

```bash
export CSS_REGRESSION_USERNAME=admin
export CSS_REGRESSION_PASSWORD=admin
masks=(--mask '#clock-wrapper' --mask '.registration-timing' --mask 'img.balloon')
uv run python scripts/css_regression.py capture --label before \
  --pages scripts/css_regression_pages.txt "${masks[@]}"
# make the change
uv run python scripts/css_regression.py capture --label after \
  --pages scripts/css_regression_pages.txt "${masks[@]}"
uv run python scripts/css_regression.py compare --before ~/.cache/date-website/css-regression/before \
  --after ~/.cache/date-website/css-regression/after
```

`scripts/css_regression_pages.txt` is the curated page list that gives every
shared and association stylesheet at least one page which loads it, including
the five seasonal event templates, so a change claimed to be neutral has
somewhere to show up. Without `--pages` the harness falls back to a small seed
list plus deterministic detail-page discovery, which does not reach the seasonal
sheets.

Some of those paths sit behind `login_required`. Supplied with credentials, the
harness signs in once per association, verifies the session against a page that
only resolves when signed in, and aborts the association rather than quietly
capturing the sign-in page as if it were the requested one. Credentials come from
`--username` and `--password`, or from the environment as above so a password
never reaches the process list. A manifest records, per association, whether the
capture was authenticated.

Three things on those pages change between two captures even when the change is
neutral, so a capture intended to reach a green verdict masks them: the wall
clock on `/members/cert/` (`#clock-wrapper`), the relative sign-up timing on an
event page (`.registration-timing`), and the animated seasonal art
(`img.balloon`). `--mask` sets `visibility: hidden` on the matching elements
only, never `display: none`, so nothing below them moves, and masked elements
stay in the computed-style probe, so a real style change on one is still
reported. A selector that matches nothing is warned about, so a mask that quietly
stopped working is visible.

Captures land under `~/.cache/date-website/css-regression/<label>/` unless
`--out` names a directory. The harness covers the six shipped variants (it skips
`demo`) at a 1600x1000 desktop viewport and a 390x844 mobile one.

`compare` exits 2 when the two captures resolved different page sets or
viewports, and exits 1 by default on any difference: `--tolerance` and
`--max-percent` default to 0, and a computed-style change fails unless
`--allow-style-changes` is passed. So the acceptance rule for a change claimed
to be appearance-neutral is that `compare` exits 0 with its defaults, meaning no
differing pixels and no computed-style change for any page or viewport. Any diff
is either a bug to fix or a change that has to be described as visual rather
than neutral.

One limit of the pixel channel is worth knowing before trusting a red run.
Adding or removing an element in `<head>` is reported but does not fail the gate:
no `<link>`, `<meta>`, `<script>` or `<style>` in the head is rendered on its
own, so it cannot shift layout. Any other element appearing or disappearing is
treated as a geometry change and does fail. Every page also warns when its final
URL differs from the requested one, so a redirect to the sign-in page shows up in
the report instead of being compared as the page that was asked for.

The stylesheet guard tests are:

```bash
date-test core.tests.test_static_css core.tests.test_css_system
```

The ratchets in `core/tests/test_css_system.py` compare the tree against a
frozen baseline in `core/tests/css_footgun_baseline.json`. Regenerate it with
`uv run python -m core.tests.test_css_system --write-baseline` only for a
reviewed, intentional change (a breakpoint added to the documented scale, an
accepted `!important`, a rule removed), never to silence an accidental
regression.
