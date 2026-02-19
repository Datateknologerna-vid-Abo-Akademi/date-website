# Playwright Element Compare Runbook

This runbook documents element-level visual parity checks between:
- legacy Django-rendered routes (`backend` templates/static)
- decoupled Next.js routes (`frontend`)

Current visual parity targets:
- Homepage hero and events under calendar
- Members login page (`/members/login`)
- Events index (`/events`)
- Events detail variants (`/events/[slug]`):
  - `default`
  - `arsfest`
  - `baal`
  - `kk100`
  - `tomtejakt`
  - `wappmiddag`

## Source of truth files
- Homepage spec: `frontend/tests/e2e/home-visual.spec.ts`
- Route parity spec: `frontend/tests/e2e/legacy-visual.spec.ts`
- Snapshot folders:
  - `frontend/tests/e2e/home-visual.spec.ts-snapshots/`
  - `frontend/tests/e2e/legacy-visual.spec.ts-snapshots/`
- Report output: `frontend/playwright-report/`
- Diff artifacts on failure: `frontend/test-results/`

## What the specs compare
- `home-visual.spec.ts`
  - Hero shell (`.header`)
  - Homepage events list under calendar (`.events-container .events`)
- `legacy-visual.spec.ts`
  - Login form card (`.members-login-page .members-form`)
  - Events index container (`.events-index-page .container-size`)
  - Events detail container (`.event-detail-page .event-detail-container`) for all required variants

Snapshot filenames include a suffix derived from `GET /api/v1/meta/site` brand/project.

## Prerequisites
1. Install frontend deps and Playwright browser once:
   - `cd frontend`
   - `npm install`
   - `npx playwright install chromium`
2. Run stack in dev:
   - from repo root: `source env.sh dev`
   - `date-start-detached`
3. Seed deterministic demo data:
   - from repo root: `date-init-demo`

Before running any visual check, confirm active association:
- `curl http://localhost:8080/api/v1/meta/site | jq -r '.data.project_name'`
- If needed, switch and reseed explicitly:
  - `date-start-detached kk`
  - `date-init-demo kk`

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
3. Verify legacy rendering at `http://localhost:8001/`.
4. Update visual baseline snapshots from legacy:
   - `cd frontend`
   - Prefer direct Playwright invocation (more reliable argument passing in PowerShell):
   - `PLAYWRIGHT_BASE_URL=http://localhost:8001 npx playwright test tests/e2e/home-visual.spec.ts --update-snapshots`
   - `legacy-visual.spec.ts` uses decoupled-only selectors and is not valid against raw legacy templates.
5. Stop override stack and remove temp file:
   - from repo root: `docker compose -f docker-compose.yml -f .tmp.legacy-visual.override.yml down`
   - delete `.tmp.legacy-visual.override.yml`
6. Return to normal stack:
   - `source env.sh dev`
   - `date-start-detached`

## Compare decoupled frontend against legacy baseline
Run the same visual specs against proxy URL:
- `cd frontend`
- `PLAYWRIGHT_BASE_URL=http://localhost:8080 npm run test:e2e:visual`

Fast iteration examples:
- Login only:
  - `PLAYWRIGHT_BASE_URL=http://localhost:8080 npm run test:e2e:visual -- -g "members login form matches approved baseline"`
- Events index only:
  - `PLAYWRIGHT_BASE_URL=http://localhost:8080 npm run test:e2e:visual -- -g "events index matches approved baseline"`
- Event detail variants only:
  - `PLAYWRIGHT_BASE_URL=http://localhost:8080 npm run test:e2e:visual -- -g "event detail variants match approved baselines"`

## Reading failures
On mismatch:
- Playwright fails with expected vs actual diff stats.
- Pixel diffs are written under `frontend/test-results/...-diff.png`.
- HTML report:
  - `cd frontend`
  - `npx playwright show-report`

## Updating baseline intentionally
Only update snapshots when the legacy reference or approved target changed:
- `PLAYWRIGHT_BASE_URL=<reference-origin> npm run test:e2e:visual -- --update-snapshots`

Do not update baselines from the decoupled app unless explicitly re-baselining.

## Troubleshooting Lessons
- Association mismatch is the most common false-positive source:
  - `source env.sh dev` alone does not guarantee the target association.
  - Always verify `project_name` from `/api/v1/meta/site` before collecting baselines.
- If backend is recreated and proxy starts returning `502`, restart proxy:
  - `docker restart datewebsite-proxy-1`
  - Nginx can keep a stale upstream IP after backend container recreation.
- `legacy-visual.spec.ts` is for decoupled DOM parity checks, not legacy-template capture.
- For snapshot updates in PowerShell, prefer `npx playwright test ... --update-snapshots` over `npm run ...` to avoid dropped flags.
- If demo reseed with reset fails (`Database ... couldn't be flushed`), use helper flow that handles association lifecycle:
  - `date-init-demo <association>`
  - If failure persists, recreate services first (`date-start-detached <association>`) then rerun.
