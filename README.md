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
5. Optional demo seed (resets DB and creates visual QA data):
   - `date-init-demo`
   - Optional association override: `date-init-demo kk` or `date-init-demo --project kk`
   - `date-init-demo <association>` now auto-starts/recreates backend/frontend services for that association before seeding.
   - Default reset mode is now automatic: DB reset happens when association change is detected (or state is unknown). Use `--no-reset` to keep DB, or `--reset` to force reset.
   - Prod safety: auto-reset is disabled in prod mode. Explicit reset requires `--reset --allow-prod-reset`, plus confirmation (`type WIPE`) or `--yes` for non-interactive runs.

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
- `.github/workflows/frontend-smoke.yml`
  - Runs on pull requests and manual trigger.
  - Boots docker stack and runs Playwright smoke tests against `http://localhost:8080`.
  - Uploads Playwright HTML report and test results artifacts.

## Key Docs
- `docs/architecture.md`
- `docs/api-contract.md`
- `docs/route-migration-matrix.md`
- `docs/docker-dev-workflow.md`
- `docs/demo-bootstrap-data.md`
- `docs/playwright-element-compare.md`
- `docs/association-qa-playbook.md`
- `docs/migration-runbook.md`
- `docs/theming-multi-association.md`
