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

## Lunch Widget
- The homepage right column embeds the official lunchmenu.fi student lunch widget below the booking card and above "Annat". The partial is `templates/common/date/components/lunch.html`, included from `templates/date/date/start.html`; its `lunch` CSS grid area sits between `bookings` and `extras` on desktop and after the news card on mobile (`static/date/date/css/homepage.css`).
- `date/templatetags/lunch.py` provides the `{% raw %}{% lunch_widget count=... heading=... wrapper_class=... %}{% endraw %}` tag. It renders `templates/common/date/components/lunch_widget.html`, returns no markup when `LUNCH_ENABLED` is off, and uses the active language when it is `sv`, `en`, or `fi`, falling back to `sv`.
- `/lunch/` renders the same widget with 10 entries and an `h2` heading. The view raises 404 when `LUNCH_ENABLED` is off, and the route is mounted only in the DaTe URLconf.
- Link `/lunch/` from the navigation (admin-managed `Länkar` or its own item); the homepage card itself does not link there, its box points at lunchmenu.fi.
- Settings: `LUNCH_ENABLED` (off in `core/settings/common.py`, on for DaTe), `LUNCH_CITY` (`turku`, used when no coordinates are set), `LUNCH_LAT`/`LUNCH_LNG` (the search origin; each association's settings module carries its kansli coordinates: DaTe Arken, kk Aurum, biocum Biocity, impuls Arken, pulterit Geohuset and sf Astra; set the env vars to override, or set the settings to `None` to use the city), `LUNCH_COUNT` (3, the sidebar count), `LUNCH_ACCENT` (`#3a80c3`).
- Set the values in the site's release environment, for example Helm `extraEnv`; the association settings carry the kansli coordinates, so the shared `.env.example` leaves them unset:

  ```dotenv
  LUNCH_ENABLED="True"
  LUNCH_CITY="turku"
  LUNCH_COUNT=3
  LUNCH_ACCENT="#3a80c3"
  # Override the association's kansli coordinates if needed:
  # LUNCH_LAT="60.4565176"
  # LUNCH_LNG="22.2796885"
  ```

- Other associations opt in by setting `LUNCH_ENABLED=true` and adding `lunch` to their `build_urlpatterns` list; their settings modules already carry the kansli coordinates. The embed keeps the box's markup until it draws, so the box's own link is what shows while the widget loads and what stays when the script can't run.
- The box's link follows the embed's own snippet: one anchor to the student lunch list of `LUNCH_CITY` for today, in the page's language, labelled with lunchmenu.fi's own wording (`Lunch i Åbo` in Swedish, `Lunch in Turku` in English, `Lounas Turku` in Finnish). `date/templatetags/lunch.py` keeps those paths and labels in `CITY_PAGES`; add a city there before pointing `LUNCH_CITY` at it, otherwise the link falls back to `https://lunchmenu.fi/`.

## Calendar Data Structure
- `format_calendar_events()` converts the event queryset into a `dict["YYYY-MM-DD"] = [event, ...]` used by the front-end calendar widget. Each date maps to a list because several events can share a day; each event includes `link`, `eventFullDate`, and `eventTitle`. The calendar JS builds the popup HTML (and the `modifier`) itself.

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
