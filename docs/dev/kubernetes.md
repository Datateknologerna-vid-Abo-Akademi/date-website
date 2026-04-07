# Kubernetes and k3s Deployment Notes

## Purpose

This guide covers the Kubernetes deployment path for `date-website`, with k3s on Hetzner Cloud and Backblaze B2 as the expected object storage provider.

Use this together with:

- `charts/date-website/values-hetzner.yaml` for the Hetzner k3s baseline
- `charts/date-website/values-backblaze-b2.example.yaml` for B2 media and PostgreSQL backup storage
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

For the current single-worker setup, `values-hetzner.yaml` keeps `web.migrateOnStartup: true` and disables the migration Job. If the web deployment is scaled above one replica, move migrations out of web startup and into a controlled migration step.

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

Do not commit real secrets to values files.

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

The backup CronJob currently installs `aws-cli` at runtime when object-storage uploads are enabled. This is acceptable for a first deployment, but a pinned backup image containing both `pg_dump` and the AWS CLI is a better long-term option.

## Operational Notes

- This one-control-plane, one-worker setup is not highly available. If the worker or its Hetzner volume is unavailable, the app and database are unavailable.
- Redis persistence is disabled in `values-hetzner.yaml` to avoid a separate 10Gi Hetzner volume for cache and broker data. This means queued Celery tasks can be lost if Redis restarts.
- Use B2 for media before scaling web replicas. Local media on a single ReadWriteOnce PVC is simpler but limits scaling and failover.
- Keep the PostgreSQL volume on `hcloud-volumes`. B2 backups protect against bad migrations and volume corruption, but they do not remove the need to monitor and test restores.
