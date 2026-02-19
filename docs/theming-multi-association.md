# Multi-Association Theming

## Previous Model
- Django chose association using `PROJECT_NAME`.
- Theme/content differences were embedded in Django templates/static and settings.

## New Model
- Frontend fetches tenant metadata at runtime from:
  - `GET /api/v1/meta/site`
- Response includes:
  - `content_variables`
  - `association_theme`
  - `navigation`
  - `feature_flags`
  - `module_capabilities`

## Legacy Visual Parity Strategy
- Frontend maps `association_theme.palette` to legacy CSS tokens (`--primaryColor`, `--linkColorLight`, etc.).
- This keeps the decoupled UI close to previous Django template styling while still using API-driven rendering.
- Navbar and dropdowns are rendered from admin-managed `navigation` data (same source as legacy templates).

## Theme Override
- Use `ASSOCIATION_THEME` env var (JSON) for deployment-specific overrides.
- Example:
  - `ASSOCIATION_THEME='{"palette":{"primary":"#123456"}}'`

## Why This Is Better
- Theme updates do not require frontend rebuild.
- Theme is centralized and versioned on backend side.
- Frontend stays generic and association-aware.

## Compatibility
- Existing per-association Django settings (`date.py`, `kk.py`, etc.) still define defaults.
- Runtime override merges into those defaults.
- Merged config is validated at startup (see `docs/association-config-schema.md`).
