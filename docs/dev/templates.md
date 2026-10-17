# Template System & Association Overrides

## How Templates Are Loaded

The project supports multiple site variants selected by `PROJECT_NAME`. Each variant has its own settings file under `core/settings/<variant>.py`, which builds the Django `TEMPLATES` `DIRS` list with the shared helpers in `core/settings/common.py`:

```python
# Variant with no inherited templates (date, kk, pulterit, demo):
TEMPLATES = build_templates('date')

# Variant inheriting another variant's templates (biocum, sf, impuls):
TEMPLATES = build_templates('biocum', parent_variants=('date',))
```

`build_templates(variant, parent_variants=())` puts the variant's own
directory **first**, then the inherited parents, then the shared common
dirs, so Django finds association templates before falling back to
`templates/common`. Use the helpers when adding a variant; do not
construct `TEMPLATES` by hand. Static dirs are built the same way with
`build_static_dirs(variant)`; note that static dirs do **not** inherit
parent variants.

## Override Pattern

Association templates **extend** the common equivalents using the same logical path:

{% raw %}
```
templates/<association>/core/footer.html  →  {% extends "core/footer.html" %}
                                                               ↓
                                             templates/common/core/footer.html
```
{% endraw %}

Django resolves the path in `{% raw %}{% extends %}{% endraw %}` by skipping the file currently being loaded (avoiding infinite recursion) and finding the next match — the common version.

This means:
- `templates/common/` defines the base structure and all available `{% raw %}{% block %}{% endraw %}` slots.
- `templates/<association>/` overrides only the blocks it needs; everything else falls through to the common template.
- Associations can also layer another association's templates before common templates. For example, Impuls uses `templates/impuls`, then `templates/date`, then `templates/common` so it can reuse the DaTe homepage layout while overriding only Impuls branding and copy.
- In a layered variant, `{% raw %}{% extends %}{% endraw %}` resolves to the parent variant's override when one exists, so blocks DaTe fills are inherited too. `templates/date/core/footer.html` puts the DaTe-only AA partner badge in `footer_right`; `templates/biocum/core/footer.html` empties that block again, and Impuls replaces it. `templates/sf/core/footer.html` does not extend the common footer at all (it is a standalone footer with no `footer_right` block), so SF replaces the whole footer. Check biocum, impuls and sf when adding content to a `templates/date/` override.

## Adding New Block Slots

If an association template needs to inject content into an area that has no block slot yet, **the slot must be added to the common template** — even as an empty block:

```django
{% raw %}
{# templates/common/core/some_template.html #}
{% block my_new_slot %}{% endblock %}
{% endraw %}
```

The association template then fills it:

```django
{% raw %}
{# templates/<association>/core/some_template.html #}
{% block my_new_slot %}
  ...association-specific content...
{% endblock %}
{% endraw %}
```

Adding an empty block to the common template is safe: associations that don't override it render nothing, so existing variants are unaffected.

**You cannot inject content into the middle of a parent template's HTML from a child template** — only into defined `{% raw %}{% block %}{% endraw %}` slots. A block defined in a child template that has no corresponding slot in the parent is a no-op; the content is silently discarded.

## Footer Social Icons

Each association lists its footer buttons in `CONTENT_VARIABLES["SOCIAL_BUTTONS"]` as `[icon, url]` pairs; an entry with a blank URL is skipped. The shared footer (`templates/common/core/footer.html`, `footer_social_buttons` block) picks the icon for each entry:

1. If the template `core/svg/social/<icon>.svg` resolves through the configured template search path, it is included inline. The `social_icon_template` tag in `date/templatetags/social_icons.py` asks Django's template loader for that path, so the whole search path is used and not just the shared directory.
2. Otherwise the entry renders as the Line Awesome icon-font class `fab <icon>`, e.g. `fa-facebook-f`.

So platforms Line Awesome covers keep using `fa-*` names, and a platform it lacks needs one SVG file to work for every association:

- Add `templates/common/core/svg/social/<name>.svg`. Name it with lowercase letters, digits and hyphens only (anything else is ignored). Give the `<svg>` a `viewBox`, `height="1em"`, `fill="currentColor"`, `focusable="false"` and `style="vertical-align: -0.125em"` so it sizes, colors and aligns like the font icons beside it without any CSS, and keep the icon's license comment.
- Give the `<svg>` `role="img"` and an `aria-label` with the platform's name spelled the way the brand writes it (`aria-label="TikTok"`). The button takes its accessible name from the icon, so this is the label screen readers announce; the file name can't carry it because it has to stay lowercase.
- Add `["<name>", "<url>"]` to the association's `SOCIAL_BUTTONS`.

To give one association a different icon, put a file at the same path in its own template directory (`templates/<association>/core/svg/social/<name>.svg`); the search order finds it before the shared file. A variant that layers another variant's templates (impuls and biocum layer `date`) or an app's `templates/` directory can supply or override an icon the same way.

Shared icons so far: `tiktok`, `linktree` (Font Awesome Free 7.3.1, CC BY 4.0). `sf` renders its own complete footer and does not use this lookup.

## Shared CSS And Element Selectors

An association's stylesheets are loaded on every page of that association, and the shared sheets under `static/common/` are loaded on every page of every association that does not shadow them. A selector that matches a bare HTML element therefore reaches parts of the page it was not written for.

The header sheets are the trap. The site header is `<nav class="navbar ...">` (from `templates/common/core/header.html`), but the pagination widgets are `<nav>` elements too: django-tables2's table pagination (`<nav aria-label="Table navigation">`, rendered on the archive documents and exam pages), the gallery fallback, and `publications-pagination`. A rule written as `nav { ... }` to style the header also painted a table's pagination bar with the header background, which on the associations whose link colour matches their background made the page numbers effectively invisible.

Rules to follow:

- Scope header rules to the header nav, e.g. `nav.navbar { ... }`. The same applies to rules that hide the chrome for a full page takeover, e.g. `nav.navbar, footer { display: none !important; }` on the Lucia and April pages.
- Scope table pagination styling to django-tables2's wrapper. `static/common/core/css/pagination.css` keeps every rule under `.table-container`, which is the wrapper the package template emits, so the news, publications and gallery paginations keep their own styling.
- Link that sheet from every site shell. The shared `templates/common/core/base.html` does, and the standalone `templates/sf/core/base.html` has to as well; a new shell needs the link too.
- `core/tests/test_static_css.py` enforces both selector rules: it fails on any unscoped `nav` selector under `static/` (a `nav` type selector must be qualified immediately by a class, id or attribute, because an ancestor alone such as `.content nav` can still contain a pagination nav) and on a `templates/**/core/base.html` that neither links the pagination sheet nor extends the common shell. `date/tests.py` renders every association's shell and asserts the link is present.
