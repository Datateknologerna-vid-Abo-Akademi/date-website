# Docker Dev Workflow

## Quick Start
1. Copy env template:
   - `cp .env.example .env`
   - Keep `backend` in `ALLOWED_HOSTS` so server-side frontend API calls to `BACKEND_API_ORIGIN` are accepted.
2. Load helpers:
   - `source env.sh dev`
3. Start stack:
   - `stack-start`
4. Open app:
   - `http://localhost:8080` (or `APP_PORT`)

## Useful Commands
- `stack-start-detached`
- `stack-stop`
- `stack-logs`
- `stack-ps`
- `stack-backend-manage migrate`
- `stack-backend-manage createsuperuser`
- `stack-test-backend`
- `stack-test-frontend`
- `stack-qa-associations`

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
