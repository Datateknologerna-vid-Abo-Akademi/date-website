# Playwright Full Parity Workflow

This workflow is for broad visual parity checks against legacy templates per association.

Playwright is executed in a dedicated Docker `e2e` container.

## Goal
- Crawl a large set of internal routes for an association.
- Compare decoupled frontend visuals (`:8080`) against legacy baselines (`:8001`).
- Cover both anonymous and logged-in member states.
- Catch event template-override drift (title-first legacy behavior) before screenshot comparison.

## Commands

Run end-to-end for one association:
```bash
source env.sh dev
date-visual-parity kk
```

Run for all associations:
```bash
date-visual-parity --all
```

Compare only (no baseline refresh):
```bash
date-visual-parity kk --no-update-baseline
```

Run an iterative chunk (fast loop):
```bash
date-visual-parity kk --chunk events --auth anon --quick --no-update-baseline
```

Run only login/auth routes:
```bash
date-visual-parity kk --chunk members-auth --auth anon --no-update-baseline
```

## Route Discovery Strategy
Route set is built from:
1. `/api/v1/meta/site` module capabilities and navigation.
2. Dynamic API expansions:
   - events, news, publications, polls, ctf, lucia, archive.
3. Optional link crawl (`a[href]`) with depth/page limits.

The manifest is attached to Playwright test output for traceability.

## Event Variant Guardrail
Before visual comparison, test verifies `template_variant` against legacy selection logic:
1. match by event title
2. fallback to slug map
3. fallback to `default`

If this fails, treat it as a logic parity bug first, not a styling bug.

## Tuning
Flags on `date-visual-parity`:
- `--no-crawl` disable DOM link crawling.
- `--max-pages <n>` cap crawl breadth.
- `--max-depth <n>` cap crawl depth.
- `--skip-template-check` bypass template guardrail.
- `--headed` run headed browser.
- `--auth <anon|member|both>` choose auth mode scope.
- `--chunk <name>` limit to a route group (repeatable).
- `--list-chunks` print available chunk names.
- `--route-prefix <path>` include only routes starting with prefix (repeatable).
- `--route-exact <path>` include only exact route paths (repeatable).
- `--route-source-prefix <source>` include only manifest source prefixes (repeatable).
- `--route-regex <pattern>` include only routes matching regex.
- `--limit <n>` cap number of routes after filtering.
- `--quick` shorthand for `--no-crawl --max-pages 40 --max-depth 1`.

Available chunks:
- `core`, `home`, `events`, `members`, `members-auth`, `news`, `pages`, `social`, `alumni`, `archive`, `publications`, `polls`, `ctf`, `lucia`, `ads`

Equivalent env vars for direct Playwright runs:
- `PLAYWRIGHT_PARITY_AUTH_MODES=anon,member`
- `PLAYWRIGHT_PARITY_ENABLE_CRAWL=1`
- `PLAYWRIGHT_PARITY_MAX_PAGES=120`
- `PLAYWRIGHT_PARITY_MAX_DEPTH=2`
- `PLAYWRIGHT_PARITY_VERIFY_TEMPLATE=1`
- `PLAYWRIGHT_PARITY_REQUIRE_VARIANTS=1` (optional strict mode; default workflow allows missing variants per association)
- `PLAYWRIGHT_PARITY_MEMBER_USERNAME=admin`
- `PLAYWRIGHT_PARITY_MEMBER_PASSWORD=admin`
- `PLAYWRIGHT_PARITY_ROUTE_CHUNKS=events,members-auth`
- `PLAYWRIGHT_PARITY_ROUTE_PREFIXES=/events,/members/login`
- `PLAYWRIGHT_PARITY_ROUTE_EXACT=/,/members/login`
- `PLAYWRIGHT_PARITY_ROUTE_SOURCE_PREFIXES=api:events,meta:navigation`
- `PLAYWRIGHT_PARITY_ROUTE_REGEX=^/events/.*`
- `PLAYWRIGHT_PARITY_ROUTE_LIMIT=25`

## Baseline Policy
- Baselines are committed under `*-snapshots/`.
- Do not update baseline from decoupled origin.
- Update only from legacy backend origin (`http://backend:8000` inside Docker network) when legacy reference changed intentionally.

## Troubleshooting
- Wrong association is the most common issue:
  - `curl http://localhost:8080/api/v1/meta/site | jq -r '.data.project_name'`
- If proxy returns `502` after recreation:
  - `docker restart datewebsite-proxy-1`
- If seeded variant set is incomplete:
  - rerun `date-init-demo <association>` and check the generated manifest attachment.
