# Decoupling Migration Runbook

## Objective
Move user-facing rendering from Django templates to Next.js while preserving existing models and business rules.

## Sequence
1. Deploy API foundation (`/api/v1`).
2. Deploy frontend app and proxy routing in parallel with existing Django pages.
3. Migrate route groups incrementally.
4. Validate parity before disabling legacy template paths.
5. After sign-off, set `LEGACY_TEMPLATE_ROUTES_ENABLED=False` to disable Django template route includes and keep API/admin as the backend surface.
   - `docker-compose.prod.yml` defaults this toggle to `False` when not explicitly set.

## Validation Checklist Per Route Group
- Rendering parity against legacy page
- Auth/permission behavior parity
- Form behavior parity (validation + success/error states)
- Association theme/content variables parity
- Admin-managed navigation parity (`StaticPageNav` ordering, dropdown ordering, login->logout behavior)
- Monitoring: error logs, response times, and session behavior

## Rollback
- Keep Django template endpoints available until sign-off.
- Route rollback is done in proxy/routing layer by sending the route group back to Django.
- API endpoints are additive and can remain enabled during rollback.
- If cutover switch is enabled, rollback by setting `LEGACY_TEMPLATE_ROUTES_ENABLED=True` and restarting backend/asgi.

## Risk Areas
- Session + CSRF in cross-origin setups (avoid by using same-domain proxy).
- Event signup edge cases (passcodes, parent event capacity, captcha).
- Event billing integration edge cases (feature flag + module enabled, invoice generation failures).
- Special event template parity is now frontend-driven via API `template_variant`; keep final UX QA per association before disabling legacy routes.
- Per-association differences in installed apps and templates (use `meta.site.data.module_capabilities` in frontend guards).
- Next.js route param API changes (Next 16 `params/searchParams` promises) can break dynamic routes if not migrated consistently.
