# Playwright Element Compare Runbook

This runbook documents how to do element-level visual parity checks between:
- legacy Django-rendered homepage (`backend` templates/static)
- decoupled Next.js homepage (`frontend`)

Current target element:
- homepage events cards under the calendar (`.events-container .events`)

## Source of truth files
- Spec: `frontend/tests/e2e/home-visual.spec.ts`
- Snapshots: `frontend/tests/e2e/home-visual.spec.ts-snapshots/`
- Report output: `frontend/playwright-report/`
- Diff artifacts on failure: `frontend/test-results/`

## What the spec compares
`home-visual.spec.ts` contains element screenshot assertions:
- hero shell (`.header`)
- events list under calendar (`.events-container .events`)

Snapshot filename suffix is derived from `GET /api/v1/meta/site` brand/project so each association keeps separate baselines.

## Prerequisites
1. Install frontend deps and Playwright browser once:
   - `cd frontend`
   - `npm install`
   - `npx playwright install chromium`
2. Run stack in dev:
   - from repo root: `source env.sh dev`
   - `date-start-detached`

## Capture baseline from legacy Django rendering
Recommended: expose backend directly on `localhost:8001` and force legacy template routes enabled, then update snapshots from that URL.

1. Create temporary compose override file `.tmp.legacy-visual.override.yml` in repo root:

```yaml
services:
  backend:
    environment:
      LEGACY_TEMPLATE_ROUTES_ENABLED: "True"
    ports:
      - "8001:8000"
```

2. Boot stack with override:
   - `docker compose -f docker-compose.yml -f .tmp.legacy-visual.override.yml up -d --build`
3. (Optional sanity check) confirm `http://localhost:8001/` is legacy-rendered HTML.
4. Update visual baseline snapshots from legacy:
   - `cd frontend`
   - `PLAYWRIGHT_BASE_URL=http://localhost:8001 npm run test:e2e:visual -- --update-snapshots`
5. Stop override stack and remove temp file:
   - from repo root: `docker compose -f docker-compose.yml -f .tmp.legacy-visual.override.yml down`
   - delete `.tmp.legacy-visual.override.yml`
6. Return to normal stack:
   - `source env.sh dev`
   - `date-start-detached`

## Compare decoupled frontend against legacy baseline
Run the same spec against proxy URL:
- `cd frontend`
- `PLAYWRIGHT_BASE_URL=http://localhost:8080 npm run test:e2e:visual`

Run only events-card test when iterating quickly:
- `PLAYWRIGHT_BASE_URL=http://localhost:8080 npm run test:e2e:visual -- -g "events cards under calendar match approved baseline"`

## Reading failures
On mismatch:
- Playwright fails test with expected vs actual dimensions and diff ratio.
- Pixel diff images are written under `frontend/test-results/...-diff.png`.
- HTML report:
  - `cd frontend`
  - `npx playwright show-report`

## Updating baseline intentionally
Only update snapshots when the legacy reference changed or parity target changed by agreement:
- `PLAYWRIGHT_BASE_URL=<reference-origin> npm run test:e2e:visual -- --update-snapshots`

Do not update baselines from the decoupled app unless explicitly re-baselining.
