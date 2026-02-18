# Testing Strategy

## Backend
- Unit tests for API serializers and response shapes.
- Unit tests for association settings schema validation.
- Integration tests for:
  - `/api/v1/meta/site`
  - `/api/v1/home`
  - `/api/v1/news*`
  - `/api/v1/events*`
    - includes `template_variant` mapping and `/events/{slug}/attendees`
  - `/api/v1/pages/{slug}`
  - `/api/v1/social*`
  - `/api/v1/ctf*`
  - `/api/v1/alumni*`
  - `/api/v1/lucia*`
  - auth session/login/logout
  - event signup/passcode edge paths (including billing invoice payload when `event_billing` is enabled)

## Frontend
- Lint and type checks in CI.
- Route rendering tests for:
  - home
  - news list/detail
  - events list/detail
  - static page detail
  - social pages
  - ctf pages
  - lucia pages
  - alumni flows

## End-to-End
- Validate through proxy URL only (same-domain behavior).
- Critical flows:
  - anonymous browsing
  - login/session persistence
  - event detail and registration
  - association switching by `PROJECT_NAME`
  - module visibility using `module_capabilities`
  - module route 404 behavior when capabilities disable a module

## Baseline Commands
- `npm run lint` (frontend)
- `npm run build` (frontend)
- `python -m compileall api` (backend quick syntax check)
