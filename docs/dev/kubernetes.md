# Kubernetes Deployment Notes (production)

## Purpose

Production runs on a Kubernetes cluster (k3s) managed with GitOps: Argo CD
watches a private operator repository and applies everything — chart,
per-site values, secrets wiring, ingress, blue-green standbys — from git.
Nothing is deployed by hand against the cluster.

This guide describes the deployment *flow* for developers working on
`date-website`. It intentionally does not include cluster addresses, access
paths, or secret locations — those live in the private operator repository
and its docs. If you are on the ops team, the operator repository is the
authoritative source; keep this file in sync with it when the flow changes.

Use this together with:

- `charts/date-website/` — the Helm chart this repository publishes
- `docs/dev/operations.md` — day-to-day app operations
- `README.md` — local development and Docker Compose workflows

## Environment model

- **`main`** is the development branch. Every push to `main` builds a
  container image and publishes it to GHCR as `<sha>` and `qa`.
- **QA and production are image environments, not branches.** An image is
  tested as `qa` first, then promoted to production.
- **SemVer release tags** (`vX.Y.Z`) are the production promotion
  mechanism. A release tag promotes the already-built image to the
  production aliases (`prod`, `latest`, and the `vX.Y.Z`/`vX.Y`/`vX`
  family) — no rebuild.
- The `promote_production.yaml` workflow can also promote an arbitrary
  existing tag (e.g. a QA-tested SHA) to `prod`/`latest` manually.

## Image pipeline

| Trigger | Image tags pushed |
|---|---|
| push to `main` | `:qa`, `:<commit-sha>` |
| SemVer tag `vX.Y.Z` | `:vX.Y.Z`, `:vX.Y`, `:vX`, `:prod`, `:latest` |
| manual `promote_production` | `:prod`, `:latest` from a chosen existing tag |

Notes:

- `qa`, `prod`, and `latest` are moving aliases — code should not assume they
  are immutable. Deployment targets pin what they want (see below).
- The release-tag job waits for the SHA-tagged image from the `main` build,
  then reuses that digest instead of rebuilding — tag the commit whose
  `main` build went green.
- Workflows: `docker_build.yaml`, `release_tag.yaml`,
  `promote_production.yaml`.

## The Helm chart

The chart lives in `charts/date-website/` and is published as an OCI chart
to GHCR by `helm_chart.yaml` whenever chart files change on `main`. Bump
`charts/date-website/Chart.yaml` `version` on any template or values change;
deployments pin the immutable chart version.

The chart deploys:

- Django/Gunicorn web deployment
- Daphne ASGI deployment for WebSocket traffic
- Celery worker deployment
- Optional PostgreSQL StatefulSet (disabled in production — see below)
- Valkey/Redis StatefulSet
- Traefik-compatible `Ingress`, or Gateway API resources
- optional migration Job

The web deployment runs `migrateOnStartup` in the production values. If the
web replica count is ever raised above 1, move migrations out of startup
into the migration Job so two pods cannot race.

## How production actually runs (summary)

- One release per association (currently: date, kk, biocum, pulterit, sf,
  qa), each in its own namespace with its own `PROJECT_NAME`, hosts,
  settings module, media prefixes, database, and secrets.
- **Databases are shared engines, not per-release.** A shared PostgreSQL
  (and MongoDB/MariaDB for other apps) runs in the cluster; each site gets
  its own database and user inside it. The chart's built-in PostgreSQL is
  disabled (`postgresql.enabled: false`, `database.external` used).
- **Media is S3-compatible object storage**, not local PVCs. The chart's
  local media PVC is not used in production.
- **Optional custom media domains** (`media.s3.privateCustomDomain` /
  `media.s3.publicCustomDomain`, host only, no scheme) switch media URLs to a
  domain served by a Cloudflare Worker in the operator repository. The Worker
  forwards requests to the S3 endpoint, rewriting the Host header to the S3
  endpoint host (the hostname the URL was signed against) and preserving path
  and query. Public media URLs become unsigned `https://<domain>/<location>/<key>`;
  private media URLs stay presigned, with only the host swapped, so the SigV4
  signature still validates.
- **The site Ingress lives outside the chart**, in the operator repository,
  so blue-green cutover can flip the backend service names without a chart
  change (see below).
- **TLS** is issued per site by cert-manager (Let's Encrypt, DNS-01) and
  terminated at the ingress.

## Deploying a release (the flow)

1. A SemVer tag is cut (or `promote_production` is run) — the image is now
   available as `prod`/`latest`.
2. In the operator repository, the site's values file pins the image tag
   (`image.tag`). A release that includes database migrations carries that
   pin together with its migrations.
3. Commit + push to the operator repository. Argo CD detects the change and
   syncs the release.
4. Verify: site responds over HTTPS, `/healthz/` and `/readyz/` are green.

The operator repository holds:

- the Argo CD Application per site (chart source + per-site values)
- per-site values files (secrets are referenced by name, never inline)
- the blue-green standbys and the ingress manifests
- the deploy tooling (see below)

## Redis ownership

PostgreSQL is shared across associations per database, and Redis must be
treated the same way. Two sanctioned layouts:

- **One Redis per association**, shared by its live and standby releases.
  The live release keeps `redis.enabled: true`; the standby sets
  `redis.enabled: false` and `redis.externalUrl` to the live release's
  Redis service (e.g. `redis://<live-release>-redis:6379`). Live and
  standby must never get separate Redis instances: a separate standby
  broker strands queued Celery tasks and splits Channels group state
  during cutover. When roles switch, the Redis service itself does not
  move: the old live's Redis keeps serving, and only the deployments
  change.
- **One shared standalone Redis instance** (not Redis Cluster: it does not
  support logical databases beyond 0) with a per-association logical
  database: `redis.enabled: false` + a pathless `redis.externalUrl` per
  site, with a unique `redis.database` number per association (0-15, the
  default Redis range). The database number is applied to the cache,
  Channels, and Celery broker and result backend, so queues and keys
  cannot collide.

Example: with one cluster Redis at `redis://redis.internal:6379`, site A
uses `redis.database: 0`, site B `redis.database: 1`, and both releases of
each site point at the same URL.

Ephemeral Redis implies an accepted task-loss model on broker loss: the
database backup does not preserve queued Celery tasks. Tasks that must
survive need a durable source of truth with reconciliation/re-enqueue, or
a durable broker; keep the backup/restore pipeline for database data only.

## Blue-green deploys (zero-downtime)

Every site has a **standby release** (same chart, `fullnameOverride`,
shares the site's database and secrets, no ingress) that is scaled to zero
between deploys. A deploy:

1. dumps the site's database first (the rollback mechanism)
2. sets the new image tag on the standby → Argo syncs it → the standby runs
   migrations on startup while the live site keeps serving
3. smoke-tests the standby, then flips the ingress backend service names to
   the standby (in-place, no traffic gap)
4. soaks, keeping the old stack as the rollback target, then scales the old
   stack to zero

**Database migration rule (important):** the standby *shares* the site's
database, so a destructive migration breaks the live site the moment the
standby migrates — not at cutover. Therefore:

- **Expand-contract (additive) migrations** — new nullable columns/tables,
  no data reshapes the old code reads — are safe and deploy zero-downtime.
- **Destructive migrations** — drops, renames, column type changes — must
  ship as two releases: an additive "expand" release, then a later "contract"
  release that cleans up. The deploy tooling gates on the live site's health
  after the standby migrates and aborts + restores the dump if the live site
  broke, but it cannot make a destructive migration zero-downtime.

## Secrets

- Production secrets live in Kubernetes secrets created out-of-band; site
  values reference them via `secret.existingSecret`. Nothing secret goes in
  values files or git.
- Sealed copies (encrypted, cluster-bound) are kept in the operator
  repository so a rebuild can recreate them.
- After rotating a secret, restart the site's deployments (pod checksum
  annotations do not see external secret changes).

## Backups

- The cluster runs nightly restic backups to Backblaze B2, taken from the
  database engines directly (dumps of every site database). Retention is
  managed in restic.
- The chart's backup CronJob is **not** used in production (the cluster-level
  pipeline supersedes it); it remains available for self-hosted installs.
- Restore is a documented, tested drill in the operator repository.

## Operational notes

- The cluster is not highly available by design: a single set of nodes,
  single database engines, single ingress plane. Bounded blast radius and
  tested restore are the availability story.
- Redis persistence is disabled in production values — queued Celery tasks
  can be lost if Redis restarts. Celery retries/cron are the backstop.
- Resource requests in `values-hetzner.yaml` are based on observed
  production usage: web is the largest process (~300–450Mi), Celery ~250Mi,
  ASGI ~90Mi. Revisit after sustained traffic or big uploads.
- Media must stay on S3-compatible storage before web replicas are ever
  scaled up; a local RWO PVC would block scaling and failover.
