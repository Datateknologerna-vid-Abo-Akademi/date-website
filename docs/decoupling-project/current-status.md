# Decoupling Project Status

Last updated: 2026-02-26

## Direction (Locked)
- Keep a **single shared Next.js frontend**.
- Keep **separate Django backends per association** (low blast radius, isolated admin/runtime).
- Route by host at gateway (`date.lvh.me`, `kk.lvh.me`, `biocum.lvh.me`, `on.lvh.me`, `demo.lvh.me`).

## Completed
- Runtime-driven frontend metadata/theming contract via `/api/v1/meta/site`.
- Canonical static page route moved to `/p/[slug]` with compatibility redirect from `/pages/[slug]`.
- Frontend nav rewrite for backend links starting with `/pages/` to load `/p/` directly.
- Host-context propagation and safer API fetch defaults for session-sensitive requests.
- Dev multi-association stack added:
  - `docker-compose.multi-assoc.yml`
  - `infra/nginx/dev.multi-assoc.conf`
  - `date-start-multi` / `date-stop-multi`
- Multi-host QA automation:
  - `scripts/multi_host_qa.py`
  - `date-qa-hosts`
  - CI workflow: `.github/workflows/multi-host-qa.yml`
- Host-matrix frontend smoke coverage (opt-in Playwright):
  - `frontend/tests/e2e/multi-host-smoke.spec.ts`
  - Verifies host-specific `/api/v1/meta/site` and rendered `body[data-association]`.
- Multi-association seed helper with isolated databases:
  - `date-init-demo-multi`
  - Creates/uses per-association databases and runs migrate + `seed_visual_demo --reset` for each backend.

## Recently Resolved
- Multi-host QA failures caused by missing `*.lvh.me` entries in active `.env` `ALLOWED_HOSTS`.
- Proxy startup failure in `dev.multi-assoc.conf` due to duplicate capture variable name.
- Cross-host homepage/theme bleed due to host-varying data caching.

## In Progress
- Stabilizing host-routed multi-association local workflow end-to-end.
- Ensuring association-specific homepage visuals (theme classes, hero SVG, title) are consistently correct by host.

## Remaining High-Priority Work
1. Finalize production host-routing documentation/config equivalent to dev multi-assoc mode.
2. Review and simplify any now-redundant single-backend tenant-resolution assumptions.

## Success Criteria for Current Phase
- Switching hosts changes association identity and theme reliably without restarts.
- `/api/v1/meta/site` returns correct `project_name` per host.
- Nav/pages/routes behave association-safely based on module capabilities.
- QA scripts and CI catch host-routing regressions automatically.
