# Template System & Association Overrides

## How Templates Are Loaded

The project supports multiple site variants selected by `PROJECT_NAME`. Each variant has its own settings file under `core/settings/<variant>.py`, which controls the Django `TEMPLATES` `DIRS` list:

```python
TEMPLATES = [{
    'DIRS': [
        'templates/<association>',
        *COMMON_TEMPLATE_DIRS,  # includes 'templates/common'
    ],
    ...
}]
```

The association-specific directory is listed **first**, so Django finds association templates before falling back to `templates/common`.

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
