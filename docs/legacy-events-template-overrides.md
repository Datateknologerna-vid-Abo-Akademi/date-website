# Legacy Events Template Overrides (Django Monolith)

Last updated: 2026-02-19

## Scope

This file documents which `events/*` templates are actually selected in the legacy Django monolith, and which association-specific template overrides are in effect.

Primary sources:
- `backend/events/views.py`
- `backend/core/settings/date.py`
- `backend/core/settings/kk.py`
- `backend/core/settings/biocum.py`
- `backend/core/settings/on.py`
- `backend/core/settings/demo.py`
- `backend/templates/*/events/*`

## Runtime template selection in legacy events view

Source: `backend/events/views.py:22`, `backend/events/views.py:35`, `backend/events/views.py:63`.

- `/events/` uses `events/index.html`.
- `/events/<slug>/` defaults to `events/detail.html`.
- If passcode is required and not validated, it uses `events/event_passcode.html`.
- Special templates are selected by event title first, then by slug.

### Event-specific template overrides (employed)

Source map: `backend/events/views.py:66` and `backend/events/views.py:75`.

| Match type | Value(s) | Selected template |
|---|---|---|
| Title | `årsfest`, `årsfest 2026`, `årsfest gäster` | `events/arsfest.html` |
| Title | `100 baal` | `events/kk100_detail.html` |
| Title | `baal` | `events/baal_detail.html` |
| Title | `tomtejakt` | `events/tomtejakt.html` |
| Title | `wappmiddag` | `events/wappmiddag.html` |
| Slug | `baal` | `events/baal_detail.html` |
| Slug | `tomtejakt` | `events/tomtejakt.html` |
| Slug | `wappmiddag` | `events/wappmiddag.html` |
| Slug | `arsfest`, `arsfest_stipendiater`, `arsfest26` | `events/arsfest.html` |
| Slug | `on100_main`, `on100_student`, `on100_alumn`, `on100_guest`, `on100_secret`, `on100_stippe` | `events/arsfest.html` |

## Association-level template override files

Django resolves templates by `TEMPLATES[0].DIRS` order, then falls back to `templates/common`.

### Effective override matrix

| Association setting | Template DIR order (events-relevant) | Event template override files present | Effective behavior |
|---|---|---|---|
| `date` | `templates/date` -> `templates/common` | `templates/date/events/arsfest.html` | Overrides common `events/arsfest.html` |
| `kk` | `templates/kk` -> `templates/common` | None under `templates/kk/events/` | Uses common event templates |
| `on` | `templates/on` -> `templates/common` | `templates/on/events/index.html`, `templates/on/events/arsfest.html` | Overrides common `events/index.html` and `events/arsfest.html` |
| `biocum` | `templates/biocum` -> `templates/date` -> `templates/common` | None under `templates/biocum/events/` | Inherits `templates/date/events/arsfest.html`; other event templates from common |
| `demo` | `templates/demo` -> `templates/common` | None under `templates/demo/events/` | Uses common event templates |

## Non-page event template overrides

For ON there are also event email template overrides:
- `backend/templates/on/events/emails/confirmation_email.html`
- `backend/templates/on/events/emails/free_confirmation_email.html`

These are used by billing confirmation email rendering (`events/emails/*.html`).

## Legacy event templates present but not selected by current public events routes

The following templates exist in `backend/templates/common/events/` but are not referenced by current `events` URL patterns or `EventDetailView.get_template_names()`:
- `kk100_index.html`
- `kk100_anmalan.html`
- `baal_anmalan.html`

They appear to be legacy/stale unless rendered from custom code outside current `events` routes.
