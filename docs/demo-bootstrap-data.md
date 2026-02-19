# Demo Bootstrap Data

This document describes the dynamic demo-data workflow for manual visual checks and feature checks.

## Quick Start
1. Load aliases:
   - `source env.sh dev`
2. Start stack:
   - `date-start`
3. Seed demo data:
   - `date-init-demo`

`date-init-demo` runs:
- `date-manage migrate --noinput`
- `date-manage seed_visual_demo --reset`

## Default Credentials
- Admin:
  - username: `admin`
  - password: `admin`
- Additional test users are also seeded with a shared member password (`member` by default).

## App-Aware Seeding
The seed command only creates data for apps enabled by the active association settings module (`PROJECT_NAME`).

Examples:
- If `news` is enabled, news posts and categories are seeded.
- If `events` is enabled, dynamic events (past/current/upcoming) and registration data are seeded.
- If `staticpages` is enabled, navigation categories and page links are seeded.
- Disabled apps are skipped automatically.

## Dynamic Dates
Event/news dates are generated relative to the seed run time, so homepage cards and calendar content stay relevant.

Use a fixed anchor date when needed:
- `date-manage seed_visual_demo --reset --base-date 2026-02-19`

## Optional Overrides
You can override credentials/password defaults via environment variables:
- `DATE_DEMO_ADMIN_USERNAME`
- `DATE_DEMO_ADMIN_PASSWORD`
- `DATE_DEMO_MEMBER_PASSWORD`

They are included in `.env.example` and `backend/.env.example`.

You can also override per run:
- `date-manage seed_visual_demo --reset --admin-username admin --admin-password admin --member-password member`

## Safety
`--reset` flushes the database. Use this only in local/dev environments where data loss is acceptable.
