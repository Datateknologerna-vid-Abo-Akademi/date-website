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
