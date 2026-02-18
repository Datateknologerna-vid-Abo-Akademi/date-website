# Decoupled Architecture

## Current Target
- `backend/` is the system of record for data, auth, business logic, background workers, and admin.
- `frontend/` is the user-facing web app built with Next.js App Router.
- API boundary is `backend/api/*` exposed as `/api/v1/*`.
- Reverse proxy (`infra/nginx/*.conf`) routes:
  - `/api/*`, `/admin/*`, `/media/*`, `/static/*` -> Django
  - all other routes -> Next.js

## Multi-Association
- Association is still selected in Django via `PROJECT_NAME` (`date`, `kk`, `biocum`, `on`, `demo`).
- Frontend theme is now runtime-driven through `GET /api/v1/meta/site`.
- `ASSOCIATION_THEME` env JSON can override per deployment without frontend rebuild.
- Optional route groups are exposed through `enabled_modules` in the same payload, so frontend navigation and pages stay association-safe.

## Decoupling Strategy
- Models remain in Django.
- Template-rendering endpoints are being replaced by API endpoints and Next.js routes.
- Django admin remains unchanged.

## Services
- `backend` (WSGI): API + admin + media/static serving.
- `asgi`: websocket support.
- `celery`: async jobs.
- `db`: PostgreSQL.
- `redis`: broker/cache/channel layer.
- `frontend`: Next.js app.
- `proxy`: single entrypoint for local/prod-like environments.
