# Translation System Notes

## Overview

The project has three translation layers that work together:

1. Django locale files translate static UI strings from templates, forms, and Python code.
2. `django-modeltranslation` adds per-language database fields for dynamic content such as event titles and static-page navigation labels.
3. Language-aware routing and cookies decide which language a request should render in.

Swedish (`sv`) is the default language. English (`en`) and Finnish (`fi`) become active only when `ENABLE_LANGUAGE_FEATURES=True`.

## Supported Languages

- Default language: `sv`
- Optional languages: `en`, `fi`
- Settings source: `core/settings/common.py`

Important settings:

- `LANGUAGE_CODE = "sv"`
- `ALL_LANGUAGES = (("sv", "Svenska"), ("en", "English"), ("fi", "Suomi"))`
- `ENABLE_LANGUAGE_FEATURES` controls whether the project exposes all languages or only Swedish
- `LOCALE_PATHS = ("locale",)` points Django to the `.po` and `.mo` files

When `ENABLE_LANGUAGE_FEATURES=False`:

- `LANGUAGES` is reduced to Swedish only
- the public/admin language switchers are hidden
- attempts to switch to `en` or `fi` fall back to `sv`

## Layer 1: Static UI Translations

Use Django's normal i18n system for strings that live in code or templates.

Typical sources:

- template strings wrapped in <code>&#123;% trans %&#125;</code> or <code>&#123;% blocktrans %&#125;</code>
- Python strings wrapped in `gettext`, `gettext_lazy`, or `_()`
- model field labels and admin labels

Locale files live here:

- `locale/sv/LC_MESSAGES/django.po`
- `locale/en/LC_MESSAGES/django.po`
- `locale/fi/LC_MESSAGES/django.po`

Common workflow:

```bash
django-admin makemessages -l sv -l en -l fi
django-admin compilemessages
```

What this does:

- `makemessages` scans templates and Python files for translatable strings and updates the `.po` files
- `compilemessages` converts `.po` files into `.mo` files that Django actually loads at runtime

## Layer 2: Dynamic Content Translations

Static UI strings are not enough for this project because editors need translated versions of database content. That is handled by `django-modeltranslation`.

The project registers translated fields in these files:

- `events/translation.py`
- `news/translation.py`
- `polls/translation.py`
- `staticpages/translation.py`

Examples of translated model fields:

- `Event.title`, `Event.content`
- `Post.title`, `Post.content`
- `Category.name`
- `Question.question_text`, `Choice.choice_text`
- `StaticPageNav.category_name`
- `StaticUrl.title`

When a field is registered for translation, `django-modeltranslation` creates language-specific columns such as:

- `title_sv`
- `title_en`
- `title_fi`

The admin then exposes those fields through translated tabs or translated inlines when language features are enabled.

## Adding Translation Support to a New Model

1. Add or update the app's `translation.py`.
2. Register the model with `TranslationOptions`.
3. List the base field names in `fields = (...)`.
4. Create and commit the migration that adds the translated database columns.
5. Backfill existing values into the new language-specific fields if needed.

Example:

```python
from modeltranslation.translator import register, TranslationOptions
from myapp.models import Thing


@register(Thing)
class ThingTranslationOptions(TranslationOptions):
    fields = ("title", "content")
    languages = ("sv", "en", "fi")
```

After adding a new translated field to an existing model:

- run migrations so the new `*_sv`, `*_en`, and `*_fi` columns exist
- run `python manage.py update_translation_fields` to copy the current base-field values into the translated columns when appropriate

Without that backfill step, old content may exist only in the original field and appear missing in translated admin tabs.

## CKEditor5 and Other Custom Field Types

This project uses CKEditor5-backed content in places that are also translated. `django-modeltranslation` needs custom-field support enabled for that to work cleanly.

The setting already exists in `core/settings/common.py`:

```python
MODELTRANSLATION_CUSTOM_FIELDS = (
    "CKEditor5Field",
)
```

If you introduce another non-standard field type that should be translated, update that setting and verify the admin/widget behavior.

## Layer 3: Language Selection and Canonical URLs

Routing and language state are handled by Django plus a few project-specific helpers.

Key files:

- `core/urls/common.py`
- `date/views.py`
- `date/middleware.py`
- `date/language_utils.py`
- `staticpages/templatetags/localized_urls.py`

How it works:

- shared route builders expose canonical unprefixed URLs
- `set_language` stores the user's choice in Django's language cookie
- `LangMiddleware` activates the language resolved from the cookie, then the default language
- `USE_ACCEPT_LANGUAGE_HEADER=True` lets an association use `Accept-Language` when no supported cookie value is set
- `localize_url()` normalizes internal paths to the canonical unprefixed form

Precedence rules:

1. Language cookie wins when present
2. `Accept-Language` is used only when `USE_ACCEPT_LANGUAGE_HEADER=True`
3. The project falls back to Swedish

## Linking Correctly in Templates and Stored URLs

For internal links:

- prefer `reverse(...)` in Python
- prefer <code>&#123;% url %&#125;</code> in templates
- use the `localized_url` template filter for internal paths stored in the database or hardcoded as plain strings

Examples:

{% raw %}
```django
<a href="{% url 'events:index' %}">...</a>
<a href="{{ '/news/'|localized_url }}">...</a>
<a href="{{ page.url|localized_url }}">{{ page.title }}</a>
```
{% endraw %}

For external links:

- keep absolute URLs absolute
- do not run `localized_url` on `https://...`, `mailto:...`, `tel:...`, anchors, or JavaScript URLs

`date.language_utils.localize_url()` already skips those cases.

## Admin Behavior

The admin adapts based on `ENABLE_LANGUAGE_FEATURES`.

When enabled:

- translated models use `TabbedTranslationAdmin` or `TranslationTabularInline`
- the custom admin template shows a language switcher
- editors can fill language-specific content from the admin UI

When disabled:

- the project falls back to ordinary Django admin classes
- only Swedish is active

Relevant files:

- `events/admin.py`
- `news/admin.py`
- `polls/admin.py`
- `staticpages/admin.py`
- `templates/common/admin/base_site.html`

## Tests and Local Development

The test settings explicitly enable language features and ensure locale files are compiled.

Relevant files:

- `core/settings/test.py`
- `core/translation_compiler.py`
- `date/tests.py`

`core.translation_compiler.ensure_compiled_translations()` exists so tests can run without depending on an external `compilemessages` binary at test time.

For translation-content QA outside the test suite, you can also run:

```bash
python scripts/validate_translations.py
```

That script fails if a required locale catalog is missing, contains fuzzy entries, or still has untranslated strings.

When you change translation behavior, cover at least these cases:

- the selected language renders the expected page copy
- the language cookie overrides the `Accept-Language` header
- the language switcher redirects back to the same canonical unprefixed page
- admin language controls appear only when language features are enabled
- stored internal URLs remain canonical through `localized_url`

## Recommended Workflow

### Translating static strings

1. Mark strings with Django translation helpers.
2. Run `django-admin makemessages -l sv -l en -l fi`.
3. Edit the `.po` files.
4. Run `django-admin compilemessages`.
5. Smoke-test pages in Swedish and at least one non-default language on the same unprefixed URL.

### Translating existing model content

1. Register the model fields in `translation.py`.
2. Create and apply migrations.
3. Run `python manage.py update_translation_fields`.
4. Review the translated admin UI.
5. Add or update test coverage.

### Adding localized navigation or stored URLs

1. Store internal paths as relative URLs when possible, for example `/news/`.
2. Render them through `localized_url`.
3. Verify switching languages keeps the target on the same canonical unprefixed path.

## Common Pitfalls

- Forgetting to run `compilemessages` after editing `.po` files
- Using absolute internal URLs in stored navigation data, which prevents locale rewriting
- Adding translated fields without backfilling existing content
- Assuming language features are always on in every environment
- Updating templates for translated copy but not smoke-testing `ENABLE_LANGUAGE_FEATURES=False`
