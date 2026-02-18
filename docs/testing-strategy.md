# Testing Strategy

## Backend
- Unit tests for API serializers and response shapes.
- Integration tests for:
  - `/api/v1/meta/site`
  - `/api/v1/home`
  - `/api/v1/news*`
  - `/api/v1/events*`
  - `/api/v1/pages/{slug}`
  - `/api/v1/social*`
  - `/api/v1/ctf*`
  - `/api/v1/alumni*`
  - `/api/v1/lucia*`
  - auth session/login/logout
  - event signup/passcode edge paths

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
  - module visibility using `enabled_modules`

## Baseline Commands
- `npm run lint` (frontend)
- `npm run build` (frontend)
- `python -m compileall api` (backend quick syntax check)
