# Association Config Schema

Association settings are validated at startup using `core.settings.validation.validate_association_settings`.

## Required Settings

### `CONTENT_VARIABLES` (dict)
Required keys:
- `SITE_URL` (non-empty string)
- `ASSOCIATION_NAME` (non-empty string)
- `ASSOCIATION_NAME_SHORT` (non-empty string)
- `ASSOCIATION_EMAIL` (non-empty string)
- `SOCIAL_BUTTONS` (list of `[icon, url]` string pairs)

### `ASSOCIATION_THEME` (dict)
Required keys:
- `brand` (non-empty string)
- `font_heading` (non-empty string)
- `font_body` (non-empty string)
- `palette` (dict)

Required `palette` keys (all non-empty strings):
- `background`
- `surface`
- `text`
- `text_muted`
- `primary`
- `secondary`
- `accent`
- `border`

### `FRONTEND_DEFAULT_ROUTE` (string)
- Must start with `/`.

### `EXPERIMENTAL_FEATURES` (list of strings)
- Feature flags used by backend/frontend capability logic.

### `INSTALLED_APPS` (list)
- Used to validate feature/app consistency.

## Conditional Requirements

### Event billing
If `EXPERIMENTAL_FEATURES` contains `event_billing`:
- `billing` must exist in `INSTALLED_APPS`.
- `BILLING_CONTEXT` must be defined with:
  - `INVOICE_RECIPIENT`
  - `IBAN`
  - `BIC`

## Notes
- Keep association-specific defaults in `core/settings/{association}.py`.
- `ASSOCIATION_THEME` may still be overridden using `ASSOCIATION_THEME` env JSON, and the merged result is validated.
