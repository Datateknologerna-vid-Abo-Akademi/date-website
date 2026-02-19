# Docker Dev Workflow

## Quick Start
1. Copy env template:
   - `cp .env.example .env`
   - Keep `backend` in `ALLOWED_HOSTS` so server-side frontend API calls to `BACKEND_API_ORIGIN` are accepted.
   - Keep `LEGACY_TEMPLATE_ROUTES_ENABLED=True` in dev unless you explicitly want to test full decoupled cutover behavior.
2. Load helpers:
   - `source env.sh dev`
3. Start stack:
   - `date-start`
   - Override association quickly: `date-start kk` (or `date-start --project kk`)
4. Open app:
   - `http://localhost:8080` (or `APP_PORT`)

## Hot Reload Notes
- Frontend hot reload is expected in dev (`next dev`).
- On Docker Desktop bind mounts (especially Windows/macOS), file events can be missed.
- Dev compose now enables polling watchers for frontend:
  - `WATCHPACK_POLLING=true`
  - `CHOKIDAR_USEPOLLING=true`
- Dev compose also runs Next with `--webpack` for more reliable file watching in containers.
- After changing this config, restart the frontend container (`date-stop` then `date-start`).

## Troubleshooting
- Verify association before visual/style QA:
  - `curl http://localhost:8080/api/v1/meta/site | jq -r '.data.project_name'`
  - If not expected, switch explicitly: `date-start-detached <association>` and reseed: `date-init-demo <association>`
- If proxy starts returning `502` after backend recreate:
  - `docker restart datewebsite-proxy-1`
  - Cause: stale upstream resolution in running proxy process.
- If manual `seed_visual_demo --reset` fails with flush errors:
  - Prefer `date-init-demo <association>` (it handles service/project lifecycle).
  - If needed, recreate services first, then rerun demo init.

## Useful Commands
- `date-start-detached`
- `date-start-both`
  - starts decoupled app on `8080` and legacy template backend on `8001` using a generated temporary compose override
  - supports association override: `date-start-both kk` or `date-start-both --project kk`
- `date-visual-parity`
  - full legacy-vs-decoupled Playwright workflow (baseline + compare)
  - runs Playwright in dedicated `e2e` container (not in frontend app container)
  - default usage: `date-visual-parity kk`
  - supports: `--all`, `--no-update-baseline`, `--no-crawl`, `--max-pages`, `--max-depth`, `--skip-template-check`, `--require-all-variants`
- `date-stop-both`
- `date-project <association> <compose-args...>`
- `date-stop`
- `date-logs`
- `date-ps`
- `date-manage migrate`
- `date-init-demo`
- Override association for any helper that supports it:
  - `date-start --project biocum`
  - `date-start-detached on`
  - `date-manage --project kk showmigrations`
  - `date-init-demo demo`
- `date-init-demo` behavior:
  - If target association differs from running association, it auto-recreates `backend`, `asgi`, `celery`, `frontend`, and `proxy` for the target.
  - Reset mode defaults to auto: reset DB on association change (or unknown previous state).
  - Override reset behavior:
    - `date-init-demo --no-reset`
    - `date-init-demo --reset`
  - Prod safety:
    - auto-reset is disabled in prod mode
    - explicit reset requires `date-init-demo --reset --allow-prod-reset`
    - an additional confirmation is required: type `WIPE` interactively, or pass `--yes` for non-interactive runs
- `date-manage createsuperuser`
- `date-test-backend`
- `date-test-frontend`
- `date-qa-associations`
- `date-visual-parity`

## Demo Bootstrap
- `date-init-demo` runs migrations and then executes `seed_visual_demo --reset`.
- This flow is app-aware: it only seeds data for apps enabled in the current association settings.
- Default credentials after seed: `admin` / `admin`.
- For details and overrides, see `docs/demo-bootstrap-data.md`.

## Service Topology
- `proxy` -> entrypoint
- `frontend` -> Next.js
- `backend` -> Django API/admin
- `asgi` -> websockets
- `celery` -> workers
- `db` -> PostgreSQL
- `redis` -> broker/cache/channel layer

## Best-Practice Defaults Applied
- Version-pinned base images
- Healthchecks for critical services
- Service dependency conditions
- Log rotation options
- Named volumes for persistent data
- Environment-file based configuration
