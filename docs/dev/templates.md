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

1. If `templates/common/core/svg/social/<icon>.svg` exists, it is included inline (looked up by the `social_icon_template` tag in `date/templatetags/social_icons.py`).
2. Otherwise the entry renders as the Line Awesome icon-font class `fab <icon>`, e.g. `fa-facebook-f`.

So platforms Line Awesome covers keep using `fa-*` names, and a platform it lacks needs one SVG file to work for every association:

- Add `templates/common/core/svg/social/<name>.svg`. Name it with lowercase letters, digits and hyphens only (anything else is ignored). Give the `<svg>` a `viewBox`, `height="1em"`, `fill="currentColor"`, `focusable="false"` and `style="vertical-align: -0.125em"` so it sizes, colors and aligns like the font icons beside it without any CSS, and keep the icon's license comment.
- Give the `<svg>` `role="img"` and an `aria-label` with the platform's name spelled the way the brand writes it (`aria-label="TikTok"`). The button takes its accessible name from the icon, so this is the label screen readers announce; the file name can't carry it because it has to stay lowercase.
- Add `["<name>", "<url>"]` to the association's `SOCIAL_BUTTONS`.

To give one association a different icon, put a file at the same path in its own template directory (`templates/<association>/core/svg/social/<name>.svg`); it is found before the shared one.

Shared icons so far: `tiktok`, `linktree` (Font Awesome Free 7.3.1, CC BY 4.0). `sf` renders its own complete footer and does not use this lookup.
