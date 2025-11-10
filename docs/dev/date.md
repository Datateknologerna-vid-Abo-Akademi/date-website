# Site Shell (date app) Development Notes

## Responsibilities
- `date/views.py:index` composes the landing page context. It fetches:
  - Upcoming events (`Event` objects where `event_date_end >= now`) plus the last 31 days for calendar dots.
  - Latest three un-categorized news posts.
  - Albins Angels spotlight (news posts in that category within 10 days).
  - Ad banners (`AdUrl`) and Instagram embeds (`IgUrl`).
- Also provides simple helpers: language switch (`language` view) and custom 404/500 handlers.

## Calendar Data Structure
- `calendar_format()` converts the event queryset into a `dict["YYYY-MM-DD"] = {...}` used by the front-end calendar widget. Keys include `link`, `modifier`, `eventFullDate`, `eventTitle`, and partial HTML stub.

## Language Handling
- `language(request, lang)` normalizes `lang` to `settings.LANG_FINNISH` or `settings.LANG_SWEDISH`, calls `translation.activate()`, and redirects to the referrer. Session storage of the language is TODO’d because Django 4 changed the constant name.

## Error Views
- `handler404`/`handler500` render templates in `templates/core/` to avoid exposing stack traces in production.

## Extending
- If more widgets are added to the home page, keep the aggregation work inside `index()` minimal; heavy data should be fetched via dedicated services or cached.
- Consider moving the calendar formatting to a serializer to simplify testing.
- Add tests in `date/tests.py` for the Albins Angels logic and calendar context; file currently empty.
