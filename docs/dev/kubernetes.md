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

- `qa`, `prod`, `latest`, `vX`, and `vX.Y` are moving aliases. Production values
  set `image.pinInProduction: true`; these aliases must be paired with
  `image.digest`.
- Exact `vX.Y.Z` release tags and 40-character commit SHA tags are accepted as
  immutable tag forms. A digest can also be supplied to retain both the
  readable tag and the exact manifest identity.
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

- Django/Gunicorn web deployment (Uvicorn async worker) serving HTTP and
  WebSockets from one process pool via `core.asgi`
- Celery worker deployment
- Optional PostgreSQL StatefulSet (disabled in production — see below)
- Valkey/Redis StatefulSet
- Traefik-compatible `Ingress`, or Gateway API resources
- optional migration Job

Migrations run as a single migration Job per release. Two modes:

- **Helm hook** (default): the Job uses `post-install,post-upgrade` hooks
  and is deleted after success. This works for plain `helm
  install/upgrade`, but hook timing under GitOps reconciliation is less
  predictable and the Job does not strictly gate application startup.
- **Plain Job + Argo sync waves** (production values): set
  `migrations.job.hook: ""` and add `argocd.argoproj.io/sync-wave: "0"` via
  `migrations.job.annotations`, with `argocd.argoproj.io/sync-wave: "1"` on
  the web/celery Deployments (`.Values.<component>.annotations`).
  Argo then runs migrations to completion before rolling the application.
  The Job gets a name suffixed with the sanitized tag + a short hash of the
  tag/digest pair (kept under 63 bytes: Kubernetes mirrors the Job name
  into a pod-template label), stays completed as desired state (no TTL),
  and the previous image's Job is pruned on the next sync. (Helm's
  Release.Revision cannot suffix the name: Argo CD renders it as 1, so the
  name would never change and the second sync would fail on the immutable
  Job pod template.)

Never enable `web.migrateOnStartup` in production: it couples schema
mutation to pod readiness, re-runs on every pod restart, and races when the
replica count is above one. Keep expand-contract migration rules so old and
new pods can overlap during rollouts.

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
   (`image.tag`) and, for moving or custom tags, the image digest
   (`image.digest`). A release that includes database migrations carries that
   pin together with its migrations.
3. Commit + push to the operator repository. Argo CD detects the change and
   syncs the release.
4. Verify: site responds over HTTPS, `/healthz/` and `/readyz/` are green.

## Static files

Every production association's static is collected into the image at build
time, one tree per variant under `/code/static-collected/<PROJECT_NAME>`
(the dev-only demo variant gets no tree). Settings pick the tree matching
the runtime `PROJECT_NAME`, so every site serves build-time static and no
web pod runs `collectstatic` at startup
(`web.collectstaticOnStartup` defaults to false; keep it only for images
built before this layout).

Separate trees are required because variants define the same logical paths
with different content (e.g. `date/css/homepage.css` differs per
association); a single merged collection would silently overwrite assets.
This keeps one generic image for all variants: no per-association images,
no startup collection, no way for an image and its values to disagree on
the variant.

The build collects each variant's static concurrently into its own tree, and
collects `django-unfold` static only for the variants that run the unfold
admin skin (`USE_UNFOLD=True`: date incl. qa, pulterit, sf, impuls); kk and
biocum keep the stock admin and the dev-only demo variant gets no collected
tree. `collectstatic` only discovers app static dirs for apps in
`INSTALLED_APPS`, so a variant collected without `USE_UNFOLD=True` renders
the unfold admin with 500s on the missing `unfold/fonts/inter/styles.css`
manifest entry (2026-08-30).

If static-on-S3 (see issue) lands, collection moves from the image build to
a release-time upload into the existing per-association media bucket, and
pods stop carrying static entirely.

With static-on-S3 the runtime `{% static %}` lookups resolve through the
manifest stored in the bucket (hashed filenames, immutable CDN caching).
Two operational rules:

- Web pods must roll AFTER the release-time collectstatic upload (the
  migration Job runs at sync wave 0, web at wave 1; a failed/retried Job
  can still leave the manifest missing at web boot).
- `StaticStorage` tolerates a missing manifest: it falls back to computing
  hashed names per `{% static %}` tag, which costs one S3 round trip per
  tag (measured on qa 2026-08-30: ~70 serial calls, ~2.3 s per page
  render). The fallback result is cached with a 60-second retry interval
  (`manifest_retry_interval`), so a worker that booted too early self-heals
  on the next interval instead of staying slow until restart.

The web deployment probes are values-templated
(`web.livenessProbe`/`web.readinessProbe`): default timeout 10 s and 5
failures, so a busy render cannot kill the pod through the probe budget
(measured death spiral on qa 2026-08-30 with the old hardcoded 5 s/3).

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
2. sets the new image tag on the standby → Argo syncs it → the ordered
   migration Job runs first (sync wave 0), then the standby application
   pods start (sync wave 1) while the live site keeps serving
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

## Graceful termination

Each component gets a deliberate shutdown policy:

- **web** (`terminationGracePeriodSeconds: 70`, `preStopSleepSeconds: 2`):
  the short preStop sleep gives the ingress time to observe endpoint
  termination and stop routing new requests; on SIGTERM gunicorn drains
  in-flight requests for `gunicorn.gracefulTimeout` (60s, configured
  explicitly; the default graceful timeout is only 30s) before killing
  workers. Requests longer than the graceful timeout are cut off at the cap
  so a deploy is never held open indefinitely. WebSockets are closed when
  the worker is killed at the graceful timeout: the Uvicorn worker stops
  accepting new connections on SIGTERM and there is no application-level
  drain hook (the removed separate asgi pod behaved the same way).
- **celery** (60s grace): celery finishes active tasks on SIGTERM. With
  `CELERY_TASK_ACKS_LATE` and `CELERY_TASK_REJECT_ON_WORKER_LOST`, work that
  was acknowledged but not finished is requeued on worker loss instead of
  being dropped; tasks must tolerate redelivery. The grace period bounds
  the roll stall: short tasks finish in place, longer ones requeue to the
  new worker instead of being waited out.

### Verification

Before relying on this, verify once per environment:

- Web: tail `web` logs during a rollout; confirm gunicorn logs graceful
  worker shutdown and no 5xx for in-flight requests.
- Web (WebSockets): hold a WebSocket open through a `web` rollout and
  confirm it closes cleanly (client sees a close frame, not a hang).
- Celery: enqueue a slow task, roll the worker, confirm it finishes (or is
  requeued and runs again) and nothing is dropped silently.

## Secrets

- Production secrets live in Kubernetes secrets created out-of-band; site
  values reference them via `secret.existingSecret`. Nothing secret goes in
  values files or git.
- Sealed copies (encrypted, cluster-bound) are kept in the operator
  repository so a rebuild can recreate them.
- After rotating a secret, restart the site's deployments (pod checksum
  annotations do not see external secret changes).

## Static on S3 (optional)

Static files can be served from the same per-association public bucket as
media (prefix `static`, CDN in front via the public custom domain) instead
of the pod filesystem. Enable per site:

```yaml
media:
  s3:
    staticEnabled: true
    staticCustomDomain: ""   # defaults to publicCustomDomain
migrations:
  job:
    enabled: true            # required: the Job performs the upload
```

**Rollout ordering (critical):** the migration Job (sync wave 0, from
#1113) uploads static before application pods start. Enabling
`staticEnabled` and the upload must happen in the same release, so pods
never render S3 URLs before the bucket is populated. Rollback: flip
`staticEnabled` back; the image still carries the build-time static trees,
so old pods serve from the pod filesystem again.

Bucket requirements (one-time):

- CORS: cross-origin fonts need `Access-Control-Allow-Origin: *` on the
  bucket (or the CDN origin) for @font-face.
- Cache: hashed filenames are immutable; set
  `Cache-Control: public, max-age=31536000, immutable` on the `static`
  prefix. Old hashes expire naturally, no CDN invalidation needed.
- The CDN must serve the `static` prefix; the public custom domain already
  serves `media/public`, so the same domain works.

## Backups

- The cluster runs nightly restic backups to Backblaze B2, taken from the
  database engines directly (dumps of every site database). Retention is
  managed in restic.
- The chart's backup CronJob is **not** used in production (the cluster-level
  pipeline supersedes it); it remains available for self-hosted installs.
  It supports `startingDeadlineSeconds` / `activeDeadlineSeconds` /
  `timeZone` to bound missed and hung runs.
- Restore is a documented, tested drill in the operator repository.

## Operational notes

- The cluster is not highly available by design: a single set of nodes,
  single database engines, single ingress plane. Bounded blast radius and
  tested restore are the availability story.
- Redis persistence is disabled in production values — queued Celery tasks
  can be lost if Redis restarts. Celery retries/cron are the backstop.
- Resource requests in `values-hetzner.yaml` are based on observed
  production usage: web is the largest process (~300-450Mi, plus a small
  increment for the Channels stack now that it also serves WebSockets),
  Celery ~250Mi. Revisit after sustained traffic or big uploads.
- Chart 0.4.0 removed the separate asgi deployment: the web deployment
  serves both HTTP and WebSockets (gunicorn Uvicorn worker on `core.asgi`),
  so the `/ws` ingress/gateway route and the asgi Service are gone. Per-site
  operator values must drop their `asgi:` overrides; WebSocket traffic
  follows the normal `/` path to the web service.
- Media must stay on S3-compatible storage before web replicas are ever
  scaled up; a local RWO PVC would block scaling and failover.
