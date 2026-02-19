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

## Useful Commands
- `date-start-detached`
- `date-stop`
- `date-logs`
- `date-ps`
- `date-manage migrate`
- `date-manage createsuperuser`
- `date-test-backend`
- `date-test-frontend`
- `date-qa-associations`

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
