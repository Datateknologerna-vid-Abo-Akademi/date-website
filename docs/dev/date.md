# Site Shell (date app) Development Notes

## Responsibilities
- `date/views.py:index` composes the landing page context. It fetches:
  - Upcoming events (`Event` objects where `event_date_end >= now`) plus the last 31 days for calendar dots.
  - Latest three un-categorized news posts.
  - Albins Angels spotlight (news posts in that category within 10 days).
  - Ad banners (`AdUrl`) and Instagram embeds (`instagram.IgUrl`).
- Also provides the homepage-template selection logic, language switching endpoint, and custom 404/500 handlers.

## Homepage Variants
- `get_homepage_template_name()` returns the standard `date/start.html` template for most sites.
- With `APRIL_HOMEPAGE_ENABLED=True` (kk), it occasionally serves `date/april_start.html` on April 1st.
- kk and impuls include the shared Instagram slider (`date/components/instagram.html`, see `docs/dev/instagram.md`); impuls shows it in place of the partners section.
- Keep variant-specific homepage behavior here rather than scattering date checks through templates.

## Calendar Data Structure
- `format_calendar_events()` converts the event queryset into a `dict["YYYY-MM-DD"] = [event, ...]` used by the front-end calendar widget. Each date maps to a list because several events can share a day; each event includes `link`, `eventFullDate`, and `eventTitle`. The calendar JS builds the popup HTML (and the `modifier`) itself.

## Calendar Widget
- The homepage calendar is `vanilla-calendar-pro` 3.x, vendored at `static/common/date/js/vanilla-calendar.min.js` and `static/common/date/css/vanilla-calendar.min.css`, with identical copies under `static/date/`, `static/impuls/` and `static/pulterit/`. `templates/common/date/partials/calendar_scripts.html` builds the popup payload, initialises the widget, and reads the clicked day from the cell's `data-vc-date`.
- `static/common/date/css/vanilla-calendar-theme.css` sets the colour properties the vendored light theme reads and restores the metrics the homepage had on 2.x: 28 px circular day buttons, thin chevron arrows, the 2.x title and weekday sizes, and a six-week grid. The options pin `selectedTheme: 'light'` because only the light theme layer is vendored; a browser that prefers a dark colour scheme would otherwise set the dark theme and lose the styles.
- Day-state colours stay per association in `static/<assoc>/date/css/homepage.css`. Where an event on today keeps the event colour (date, demo, sf, impuls) the today rule carries `:not(.calendar-eventday)`; pulterit leaves it off because its 2.x rule order let today win.
- Selection is not painted. The library selects the clicked day, but the homepage calendar only navigates to an event or opens a popup, and 2.x never filled the clicked day either. The theme keeps the selected state identical to a plain day, hover included.

## Language Handling
- `set_language(request)` reads `POST["lang"]`, normalizes it through `date.language_utils.resolve_language()`, stores the choice in Django's language cookie, and redirects back to the referrer.
- If the referrer points to an internal page, `date.language_utils.strip_language_prefix()` rewrites the path back to the canonical unprefixed URL before redirecting.
- `date/middleware.py` contains the project-specific language middleware:
  - `LanguageStateMiddleware` restores the previous translation state after each request.
  - `LangMiddleware` activates the language resolved from the cookie, then Swedish by default, while ignoring URL path prefixes.
  - `USE_ACCEPT_LANGUAGE_HEADER=True` allows browser language detection before falling back to Swedish.
- Shared URL configuration uses canonical unprefixed public routes such as `/`, `/news/`, and `/events/` even when `ENABLE_LANGUAGE_FEATURES=True`.

## Error Views
- `handler404`/`handler500` render templates in `templates/core/` to avoid exposing stack traces in production.

## Middleware Notes
- `HTCPCPMiddleware` serves the custom `418` page for coffee-themed easter-egg routes.

## Extending
- If more widgets are added to the home page, keep the aggregation work inside `index()` minimal; heavy data should be fetched via dedicated services or cached.
- Consider moving the calendar formatting to a serializer to simplify testing.
- When changing language-aware redirects, test both direct unprefixed URL visits and redirects from the language switcher.
- Add tests in `date/tests.py` for homepage context selection, language switching, and calendar formatting behavior.
