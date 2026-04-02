# Site Shell (date app) Development Notes

## Responsibilities
- `date/views.py:index` composes the landing page context. It fetches:
  - Upcoming events (`Event` objects where `event_date_end >= now`) plus the last 31 days for calendar dots.
  - Latest three un-categorized news posts.
  - Albins Angels spotlight (news posts in that category within 10 days).
  - Ad banners (`AdUrl`) and Instagram embeds (`IgUrl`).
- Also provides the homepage-template selection logic, language switching endpoint, and custom 404/500 handlers.

## Homepage Variants
- `get_homepage_template_name()` returns the standard `date/start.html` template for most sites.
- For `PROJECT_NAME=kk`, it occasionally serves `date/april_start.html` on April 1st.
- Keep variant-specific homepage behavior here rather than scattering date checks through templates.

## Calendar Data Structure
- `calendar_format()` converts the event queryset into a `dict["YYYY-MM-DD"] = {...}` used by the front-end calendar widget. Keys include `link`, `modifier`, `eventFullDate`, `eventTitle`, and partial HTML stub.

## Language Handling
- `set_language(request)` reads `POST["lang"]`, normalizes it through `date.language_utils.resolve_language()`, stores the choice in Django's language cookie, and redirects back to the referrer.
- If the referrer points to an internal page, `date.language_utils.localize_url()` rewrites the path so the redirect keeps or replaces the active language prefix correctly.
- `date/middleware.py` contains the project-specific language middleware:
  - `LanguageStateMiddleware` restores the previous translation state after each request.
  - `LangMiddleware` activates the language resolved by Django's `LocaleMiddleware` or the language cookie.
- Shared URL configuration uses Django `i18n_patterns`, so public routes can appear as `/sv/...`, `/en/...`, and `/fi/...` when `ENABLE_LANGUAGE_FEATURES=True`.

## Error Views
- `handler404`/`handler500` render templates in `templates/core/` to avoid exposing stack traces in production.

## Middleware Notes
- `HTCPCPMiddleware` serves the custom `418` page for coffee-themed easter-egg routes.
- `CDNRewriteMiddleware` rewrites known storage hostnames in non-streaming responses. If you introduce new public asset hostnames, add them to `CDN_URL_TRANSFORMATIONS` in settings.

## Extending
- If more widgets are added to the home page, keep the aggregation work inside `index()` minimal; heavy data should be fetched via dedicated services or cached.
- Consider moving the calendar formatting to a serializer to simplify testing.
- When changing language-aware redirects or prefixed routes, test both direct URL visits and redirects from the language switcher.
- Add tests in `date/tests.py` for homepage context selection, language switching, and calendar formatting behavior.
