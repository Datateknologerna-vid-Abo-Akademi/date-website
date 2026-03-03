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
- Recommended operational model for low blast radius:
  - Shared frontend codebase/deployment.
  - Separate backend runtime per association.
  - Host-based routing in gateway (`date.lvh.me`, `kk.lvh.me`, etc.) to association-specific backends.
- Dev-mode multi-association topology is available via:
  - `docker-compose.multi-assoc.yml`
  - `infra/nginx/dev.multi-assoc.conf`
  - helper: `date-start-multi`
- Frontend theme is now runtime-driven through `GET /api/v1/meta/site`.
- `ASSOCIATION_THEME` env JSON can override per deployment without frontend rebuild.
- Optional route groups are exposed through `module_capabilities` in the same payload, so frontend navigation and pages stay association-safe.
- Preferred module nav labels and routes are exposed in `module_capabilities` (`label`, `nav_route`) so frontend nav is less hardcoded.
- Association-specific landing behavior is controlled by `FRONTEND_DEFAULT_ROUTE` (exposed as `default_landing_path`).
- Django route includes for module apps are now assembled through shared helpers in `core.urls.helpers`, so app/plugin toggles in `INSTALLED_APPS` do not require duplicating URL wiring in every association URLConf.
- Production cutover can disable legacy Django template routes with `LEGACY_TEMPLATE_ROUTES_ENABLED=False` while keeping API/admin and static/media endpoints available.
- Special event rendering behavior is exposed via event `template_variant` instead of Django template routing.
- Association config is validated at startup (theme/content variables/routes/feature consistency). See `association-config-schema.md`.

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
