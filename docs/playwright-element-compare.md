# Playwright Element Compare Runbook

This runbook covers two visual-parity layers between:
- legacy Django-rendered routes (`http://localhost:8001`)
- decoupled Next.js routes (`http://localhost:8080`)

Playwright execution is done in a dedicated Docker `e2e` service (not inside the `frontend` app container).

## Coverage Modes
- Targeted parity (fast): homepage/login/events targeted checks.
- Full-route parity (broad): crawls and compares all internal links found for an association, in both `anon` and `member` states.

## Source of Truth Specs
- `frontend/tests/e2e/home-visual.spec.ts`
- `frontend/tests/e2e/legacy-visual.spec.ts`
- `frontend/tests/e2e/legacy-full-parity.spec.ts`

## Snapshot and Artifact Paths
- Baselines:
  - `frontend/tests/e2e/home-visual.spec.ts-snapshots/`
  - `frontend/tests/e2e/legacy-visual.spec.ts-snapshots/`
  - `frontend/tests/e2e/legacy-full-parity.spec.ts-snapshots/`
- Runtime artifacts:
  - `frontend/playwright-report/`
  - `frontend/test-results/`

Keep baseline snapshot folders committed. Keep reports/results gitignored.

## Prerequisites
1. `source env.sh dev`
2. `date-init-demo <association>` (defaults to current project)
3. `date-start-both <association>` (ensures legacy on `:8001` and decoupled on `:8080`)

Verify association:
- `curl http://localhost:8080/api/v1/meta/site | jq -r '.data.project_name'`

## Full-Route Visual Workflow (Recommended)
Single command:
- `date-visual-parity kk`

What it does:
1. Seeds deterministic demo data.
2. Starts both frontends (legacy + decoupled).
3. Runs Playwright from the dedicated `e2e` container.
4. Updates snapshots from legacy backend service (`http://backend:8000` inside Docker network).
5. Runs decoupled comparison via proxy service (`http://proxy` inside Docker network).

Useful flags:
- `date-visual-parity kk --no-update-baseline`
- `date-visual-parity --all`
- `date-visual-parity kk --no-crawl`
- `date-visual-parity kk --max-pages 200 --max-depth 3`
- `date-visual-parity kk --skip-template-check`
- `date-visual-parity kk --chunk events --auth anon --quick --no-update-baseline`
- `date-visual-parity kk --chunk members-auth --auth anon --no-update-baseline`
- `date-visual-parity kk --route-prefix /events --route-prefix /members/login --no-update-baseline`

Chunk names:
- `core`, `home`, `events`, `members`, `members-auth`, `news`, `pages`, `social`, `alumni`, `archive`, `publications`, `polls`, `ctf`, `lucia`, `ads`

## Manual Full-Route Commands (Docker e2e)
From repo root:

1. Install deps in `e2e` volume:
```bash
docker compose run --rm --no-deps e2e sh -lc "cd /work/frontend && npm ci"
```

2. Capture/update legacy baseline:
```bash
docker compose run --rm --no-deps e2e sh -lc "cd /work/frontend && PLAYWRIGHT_BASE_URL=http://backend:8000 PLAYWRIGHT_PARITY_AUTH_MODES=anon,member PLAYWRIGHT_PARITY_ROUTE_CHUNKS=events,members-auth npm run test:e2e:legacy-full-parity -- --update-snapshots"
```

3. Compare decoupled app:
```bash
docker compose run --rm --no-deps e2e sh -lc "cd /work/frontend && PLAYWRIGHT_BASE_URL=http://proxy PLAYWRIGHT_PARITY_AUTH_MODES=anon,member PLAYWRIGHT_PARITY_ROUTE_CHUNKS=events,members-auth npm run test:e2e:legacy-full-parity"
```

## Event Template Override Gate
`legacy-full-parity.spec.ts` validates template-variant resolution against legacy rules before visual assertions:
- title-based overrides are checked first
- slug-based overrides are fallback

This prevents false visual conclusions when the decoupled variant selection logic diverges from legacy behavior.

## Targeted Parity Commands
- `PLAYWRIGHT_BASE_URL=http://localhost:8080 npm run test:e2e:visual`
- Optional filter:
  - `PLAYWRIGHT_BASE_URL=http://localhost:8080 npm run test:e2e:visual -- -g "events index matches approved baseline"`

## Failure Triage
- Open report:
  - `cd frontend`
  - `npx playwright show-report`
- Check attached manifest in failing test output:
  - includes crawled route list, source, and variant coverage
- Common causes:
  - wrong active association
  - stale proxy upstream after backend recreation (`docker restart datewebsite-proxy-1`)
  - baseline updated from wrong origin
