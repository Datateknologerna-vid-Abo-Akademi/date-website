# Date Website (Decoupled)

Monorepo with:
- `backend/`: Django API, admin, data models, workers
- `frontend/`: Next.js frontend
- `infra/`: proxy and deployment config
- `docs/`: migration and architecture documentation

## Start Full Stack (Docker)
1. Copy env template:
   - `cp .env.example .env`
2. Load helper aliases:
   - `source env.sh dev`
3. Start:
   - `date-start`
   - Optional association override: `date-start kk` or `date-start --project kk`
4. Open:
   - `http://localhost:8080`
   - Multi-association mode (single frontend + separate association backends):
     - `date-start-multi`
     - Visit:
       - `http://date.lvh.me:8080`
       - `http://kk.lvh.me:8080`
       - `http://biocum.lvh.me:8080`
       - `http://on.lvh.me:8080`
       - `http://demo.lvh.me:8080`
5. Optional demo seed (resets DB and creates visual QA data):
   - `date-init-demo`
   - Optional association override: `date-init-demo kk` or `date-init-demo --project kk`
   - `date-init-demo <association>` now auto-starts/recreates backend/frontend services for that association before seeding.
   - Default reset mode is now automatic: DB reset happens when association change is detected (or state is unknown). Use `--no-reset` to keep DB, or `--reset` to force reset.
   - Prod safety: auto-reset is disabled in prod mode. Explicit reset requires `--reset --allow-prod-reset`, plus confirmation (`type WIPE`) or `--yes` for non-interactive runs.
   - Multi-association seed with isolated DBs per association:
     - `date-init-demo-multi`
     - Uses one database per association (`MULTI_ASSOC_DB_DATE`, `MULTI_ASSOC_DB_KK`, `MULTI_ASSOC_DB_BIOCUM`, `MULTI_ASSOC_DB_ON`, `MULTI_ASSOC_DB_DEMO`).
6. Full legacy-vs-decoupled visual parity (association-aware):
   - `date-visual-parity kk`
   - optional: `date-visual-parity --all`
   - runs Playwright in dedicated `e2e` container

## Backend-Only Workflow
`backend/env.sh` is still available for backend-only development.

## Cutover Toggle
- Set `LEGACY_TEMPLATE_ROUTES_ENABLED=False` to disable legacy Django template route includes after parity sign-off.
- Keep it `True` during migration if you still need backend-rendered fallback routes.

## CI Workflows
- `.github/workflows/ci.yml`
  - Runs on push and pull requests.
  - Frontend: `npm ci`, `npm run lint`, `npm run build`.
  - Backend: dependency install + `python -m compileall backend` + `python backend/manage.py test core.tests api.tests`.
- `.github/workflows/association-qa.yml`
  - Runs nightly and on manual trigger.
  - Executes `python scripts/association_qa.py`.
  - Uploads `docs/association-qa-report.md` as a workflow artifact.
- `.github/workflows/multi-host-qa.yml`
  - Runs nightly and on manual trigger.
  - Boots multi-backend host-routed stack (`docker-compose.yml` + `docker-compose.multi-assoc.yml`).
  - Executes `python scripts/multi_host_qa.py`.
  - Uploads `docs/multi-host-qa-report.md` as a workflow artifact.
- `.github/workflows/frontend-smoke.yml`
  - Runs on pull requests and manual trigger.
  - Boots docker stack and runs Playwright smoke tests against `http://localhost:8080`.
  - Uploads Playwright HTML report and test results artifacts.

## Playwright Test Modes
- `npm run test:e2e`: required smoke suite only (CI gate).
- `npm run test:e2e:all`: all e2e specs (visual/parity suites are skipped unless enabled).
- `PLAYWRIGHT_ENABLE_VISUAL=1 npm run test:e2e:visual`: run visual suites.
- `PLAYWRIGHT_ENABLE_PARITY=1 npm run test:e2e:parity`: run legacy parity suites.
- `PLAYWRIGHT_MULTI_HOST=1 npx playwright test tests/e2e/multi-host-smoke.spec.ts`: run host-matrix smoke against `date/kk/on` hostnames.

## Key Docs
- `docs/decoupling-project/current-status.md`
- `docs/decoupling-project/architecture.md`
- `docs/decoupling-project/api-contract.md`
- `docs/decoupling-project/route-migration-matrix.md`
- `docs/decoupling-project/docker-dev-workflow.md`
- `docs/decoupling-project/demo-bootstrap-data.md`
- `docs/decoupling-project/playwright-element-compare.md`
- `docs/decoupling-project/playwright-full-parity-workflow.md`
- `docs/decoupling-project/association-qa-playbook.md`
- `docs/decoupling-project/migration-runbook.md`
- `docs/decoupling-project/theming-multi-association.md`
