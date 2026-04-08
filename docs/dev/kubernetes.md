# Kubernetes and k3s Deployment Notes

## Purpose

This guide covers the Kubernetes deployment path for `date-website`, with k3s on Hetzner Cloud and Backblaze B2 as the expected object storage provider.

Use this together with:

- `charts/date-website/values-hetzner.yaml` for the Hetzner k3s baseline
- `charts/date-website/values-backblaze-b2.example.yaml` for B2 media and PostgreSQL backup storage
- `charts/date-website/values-kk.example.yaml`, `charts/date-website/values-biocum.example.yaml`, or `charts/date-website/values-pulterit.example.yaml` for association-specific overrides
- `README.md` for local development and Docker Compose workflows

## Cluster Shape

The first production k3s target is expected to be:

- one CX23 control-plane node
- one CX33 worker node
- Hetzner Cloud Controller Manager and CSI driver installed by `hetzner-k3s` or the Terraform k3s module
- Traefik as the k3s ingress controller
- Hetzner `hcloud-volumes` storage class for PostgreSQL

The chart assumes Traefik through:

```yaml
ingress:
  className: traefik
```

Do not manually mount a Hetzner volume for PostgreSQL. Let the Hetzner CSI driver provision it from the chart's PVC by using `storageClass: hcloud-volumes`.

Use either `values-k3s.yaml` or `values-hetzner.yaml` as the cluster-specific storage preset, not both. `values-k3s.yaml` is for a generic k3s cluster using `local-path`; `values-hetzner.yaml` is for Hetzner k3s using `hcloud-volumes` and includes the resource sizing used for the planned CX33 worker.

## Helm Chart

The chart lives in:

```text
charts/date-website/
```

The chart deploys:

- Django/Gunicorn web deployment
- Daphne ASGI deployment for WebSocket traffic
- Celery worker deployment
- PostgreSQL StatefulSet
- Valkey/Redis StatefulSet
- Traefik-compatible Ingress
- optional local media PVC
- PostgreSQL backup CronJob
- optional migration Job

The base chart defaults `web.migrateOnStartup: false` to avoid migration races when `web.replicaCount` is increased. For the current single-worker Hetzner setup, `values-hetzner.yaml` overrides this to `true` and disables the migration Job. If the web deployment is scaled above one replica, move migrations out of web startup and into a controlled migration step.

The Ingress routes WebSocket traffic to the ASGI service with `asgi.wsPath`, which defaults to `/ws`.

## Multiple Associations

Run one Helm release per association. Do not route `date`, `kk`, `biocum`, and `pulterit` through the same release, because each release needs its own `PROJECT_NAME`, Django URL configuration, static/template paths, hosts, media prefixes, database, and backup prefix.

Examples:

```bash
helm upgrade --install date charts/date-website \
  --namespace date \
  --create-namespace \
  -f charts/date-website/values-hetzner.yaml \
  -f charts/date-website/values-backblaze-b2.example.yaml \
  --set secret.existingSecret=date-website-prod-secrets \
  --set image.tag='<release-tag>'
```

```bash
helm upgrade --install kk charts/date-website \
  --namespace kk \
  --create-namespace \
  -f charts/date-website/values-hetzner.yaml \
  -f charts/date-website/values-backblaze-b2.example.yaml \
  -f charts/date-website/values-kk.example.yaml \
  --set secret.existingSecret=kk-website-prod-secrets \
  --set image.tag='<release-tag>'
```

```bash
helm upgrade --install biocum charts/date-website \
  --namespace biocum \
  --create-namespace \
  -f charts/date-website/values-hetzner.yaml \
  -f charts/date-website/values-backblaze-b2.example.yaml \
  -f charts/date-website/values-biocum.example.yaml \
  --set secret.existingSecret=biocum-website-prod-secrets \
  --set image.tag='<release-tag>'
```

```bash
helm upgrade --install pulterit charts/date-website \
  --namespace pulterit \
  --create-namespace \
  -f charts/date-website/values-hetzner.yaml \
  -f charts/date-website/values-backblaze-b2.example.yaml \
  -f charts/date-website/values-pulterit.example.yaml \
  --set secret.existingSecret=pulterit-website-prod-secrets \
  --set image.tag='<release-tag>'
```

Each release should have separate `django.projectName`, `django.allowedHosts`, `django.allowedOrigins`, `ingress.hosts`, media bucket names or prefixes, backup bucket name or prefix, and Kubernetes Secret. Keeping separate namespaces is optional, but it makes secrets, PVCs, and operational commands harder to mix up.

If several associations share one B2 bucket, keep unique media locations such as `date/media`, `kk/media`, `biocum/media`, and `pulterit/media`. If they use separate B2 buckets, still keep distinct backup prefixes such as `date-website/postgresql`, `kk-website/postgresql`, `biocum-website/postgresql`, and `pulterit-website/postgresql`.

## Backblaze B2 Object Storage

Backblaze B2 should be configured through the S3-compatible API. Backblaze documents the endpoint format in its [S3-compatible API guide](https://www.backblaze.com/docs/cloud-storage-call-the-s3-compatible-api); use the endpoint for the bucket region:

```text
https://s3.<region>.backblazeb2.com
```

Example:

```text
https://s3.us-west-000.backblazeb2.com
```

B2 uses v4 signatures for the S3-compatible API. The chart example sets:

```yaml
signatureVersion: "s3v4"
addressingStyle: "path"
```

Prefer separate B2 buckets for private media, public media, and database backups:

```yaml
media:
  s3:
    privateBucketName: "date-website-private"
    publicBucketName: "date-website-public"

backups:
  objectStorage:
    bucketName: "date-website-backups"
```

This avoids depending on per-object ACL behavior. Treat public/private access as a bucket-level decision in B2.

When `media.s3.enabled: true`, the chart does not mount the local media PVC. Uploaded media goes to B2 instead of `/code/media`.

When `backups.objectStorage.enabled: true` and `backups.persistence.enabled: false`, the backup CronJob writes the dump to an `emptyDir`, uploads the compressed dump to B2, and does not allocate a separate Hetzner backup volume.

## Production Secret

Prefer a pre-created Kubernetes Secret for production values:

```bash
kubectl create namespace date-website

kubectl -n date-website create secret generic date-website-prod-secrets \
  --from-literal=SECRET_KEY='<django-secret-key>' \
  --from-literal=DB_PASSWORD='<postgres-password>' \
  --from-literal=AWS_ACCESS_KEY_ID='<b2-media-application-key-id>' \
  --from-literal=AWS_SECRET_ACCESS_KEY='<b2-media-application-key>' \
  --from-literal=OBJECT_STORAGE_ACCESS_KEY_ID='<b2-backup-application-key-id>' \
  --from-literal=OBJECT_STORAGE_SECRET_ACCESS_KEY='<b2-backup-application-key>' \
  --from-literal=EMAIL_HOST_USER='<smtp-user>' \
  --from-literal=EMAIL_HOST_PASSWORD='<smtp-password>' \
  --from-literal=CF_TURNSTILE_SECRET_KEY='<turnstile-secret>'
```

Use separate B2 application keys for media and backups if possible. The media key should only access the media buckets; the backup key should only access the backup bucket.

Do not commit real secrets to values files. If `secret.existingSecret` is not set, the chart-created Secret requires real `django.secretKey` and `database.password` values at render time.

When `secret.existingSecret` is used, pod checksum annotations cannot detect changes inside that external Secret. After rotating an external Secret, restart the affected workloads:

```bash
kubectl -n <namespace> rollout restart deploy/<release>-date-website-web
kubectl -n <namespace> rollout restart deploy/<release>-date-website-asgi
kubectl -n <namespace> rollout restart deploy/<release>-date-website-celery
```

## Deploy

Copy the B2 example values into an environment-specific private values file before production use, or override the bucket names and endpoint from CI/CD.

Typical install or upgrade:

```bash
helm upgrade --install date-website charts/date-website \
  --namespace date-website \
  --create-namespace \
  -f charts/date-website/values-hetzner.yaml \
  -f charts/date-website/values-backblaze-b2.example.yaml \
  --set secret.existingSecret=date-website-prod-secrets \
  --set image.tag='<release-tag>'
```

Set `image.tag` to a release tag or pinned image tag. Avoid deploying `master` by accident in production.

For KK, Biologica, or Pulterit, layer the matching association values file after the B2 values file so the association-specific hosts, `PROJECT_NAME`, media paths, and backup prefix override the default `date` example.

## Verify

Check Kubernetes resources:

```bash
kubectl -n date-website get pods
kubectl -n date-website get ingress
kubectl -n date-website get pvc
kubectl -n date-website logs deploy/date-website-web
```

Check Django probes through the public host after DNS and TLS are configured:

```bash
curl -fsS https://<host>/healthz/
curl -fsS https://<host>/readyz/
```

`/healthz/` only checks that the app process responds. `/readyz/` checks database and cache access.

## Backups

The Hetzner values file enables the backup CronJob by default:

```yaml
backups:
  enabled: true
  schedule: "17 2 * * *"
  retentionDays: 14
```

With the B2 override, the CronJob uploads compressed PostgreSQL dumps to:

```text
s3://<backup-bucket>/date-website/postgresql/
```

To trigger one backup manually:

```bash
kubectl -n date-website create job \
  --from=cronjob/date-website-postgresql-backup \
  date-website-postgresql-backup-manual-$(date -u +%Y%m%d%H%M%S)
```

Then inspect the job logs and confirm the object exists in B2:

```bash
kubectl -n date-website logs job/<manual-backup-job-name>
```

For object-storage uploads, prefer a pinned backup image that already contains both `pg_dump` and the AWS CLI, and keep `backups.objectStorage.installAwsCli: false`. The B2 example values intentionally keep runtime package installation disabled, so production deployments using object-storage uploads should override `backups.image` to a backup image with both tools installed. The backup job defaults to the PostgreSQL image's non-root UID/GID and sets `backups.podSecurityContext.fsGroup` so the mounted backup directory is writable. If you temporarily set `installAwsCli: true` with an Alpine image, the backup container needs a root-capable `backups.securityContext` because `apk add --no-cache aws-cli` requires package-install privileges.

`retentionDays` prunes old dump files only from the local `/backups` directory. When the B2 override uses `backups.persistence.enabled: false`, this local retention is only for the temporary `emptyDir`; remote B2 objects are not pruned by the CronJob. Configure a B2 bucket lifecycle rule for `date-website/postgresql/` if remote backup retention should be automatic.

## Operational Notes

- This one-control-plane, one-worker setup is not highly available. If the worker or its Hetzner volume is unavailable, the app and database are unavailable.
- `values-hetzner.yaml` resource requests are based on observed Docker production usage: web is the largest process at roughly 300-450Mi, Celery sits around 250Mi, ASGI around 90Mi, and idle Postgres/Redis are much smaller. Revisit requests after sustained Kubernetes traffic, especially after larger event registrations or admin uploads.
- Redis persistence is disabled in `values-hetzner.yaml` to avoid a separate 10Gi Hetzner volume for cache and broker data. This means queued Celery tasks can be lost if Redis restarts.
- Use B2 for media before scaling web replicas. Local media on a single ReadWriteOnce PVC is simpler but limits scaling and failover.
- Keep the PostgreSQL volume on `hcloud-volumes`. B2 backups protect against bad migrations and volume corruption, but they do not remove the need to monitor and test restores.
