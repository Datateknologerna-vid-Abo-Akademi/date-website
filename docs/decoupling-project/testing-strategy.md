# Testing Strategy

## Backend
- Unit tests for API serializers and response shapes.
- Unit tests for association settings schema validation.
- Integration tests for:
  - `/api/v1/meta/site`
    - includes module capability nav metadata (`label`, `nav_route`)
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
- Playwright smoke checks in CI against dockerized stack.
- Playwright visual regression for homepage parity (hero + events cards) with snapshot baselines.
- Playwright full-route legacy-vs-decoupled visual parity (association-aware crawl, anon/member states, event template override guardrail).
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
  - event `template_variant` rendering and section navigation (`#/main`, `#/anmalan`, `#/attendee-list`)
  - default event detail behavior keeps content, signup, and attendees visible without variant tabs
  - association switching by `PROJECT_NAME`
  - module visibility using `module_capabilities`
  - module route 404 behavior when capabilities disable a module

## Baseline Commands
- `npm run lint` (frontend)
- `npm run build` (frontend)
- `npm run test:e2e` (frontend required Playwright smoke suite only; requires running stack and `PLAYWRIGHT_BASE_URL`)
- `npm run test:e2e:all` (frontend full Playwright suite)
- `PLAYWRIGHT_ENABLE_VISUAL=1 npm run test:e2e:visual` (optional visual parity checks against committed snapshots)
- `PLAYWRIGHT_ENABLE_PARITY=1 npm run test:e2e:parity` (optional legacy parity checks)
- `PLAYWRIGHT_ENABLE_PARITY=1 npm run test:e2e:legacy-full-parity` (optional full-route legacy baseline parity suite)
- `python -m compileall backend` (backend quick syntax check)
- `python scripts/association_qa.py` (cross-association runtime parity and module-guard checks)
  - uses uncached `meta/site` reads in frontend to avoid stale capability data when switching `PROJECT_NAME`

## Homepage Visual Baseline Workflow
1. Generate baseline snapshots from legacy Django rendering:
   - run tests against legacy URL with snapshot update enabled
   - `PLAYWRIGHT_BASE_URL=<legacy-home-origin> npm run test:e2e:visual -- --update-snapshots`
2. Compare decoupled frontend against that baseline:
   - `PLAYWRIGHT_BASE_URL=<decoupled-origin> npm run test:e2e:visual`
3. CI/local fails when homepage visuals drift beyond threshold.
4. Detailed step-by-step (including temporary legacy backend exposure on `:8001`) is documented in:
   - `playwright-element-compare.md`

## CI Mapping
- Fast CI (`.github/workflows/ci.yml`)
  - frontend lint/build
  - backend compile check
  - backend core/api test suites (`python backend/manage.py test core.tests api.tests`)
- Frontend smoke E2E (`.github/workflows/frontend-smoke.yml`)
  - dockerized stack boot + Playwright smoke checks
  - uploads Playwright artifacts
- Association QA (`.github/workflows/association-qa.yml`)
  - scheduled/manual full runtime association checks
  - uploads QA markdown report artifact
