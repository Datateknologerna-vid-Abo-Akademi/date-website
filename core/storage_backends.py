import logging
import threading
import time
from urllib.parse import urlsplit, urlunsplit

from django.conf import settings
from django.contrib.staticfiles.storage import ManifestFilesMixin
from storages.backends.s3boto3 import S3Boto3Storage
from storages.utils import clean_name
from whitenoise.storage import CompressedManifestStaticFilesStorage

logger = logging.getLogger(__name__)


class NonStrictManifestStaticFilesStorage(CompressedManifestStaticFilesStorage):
    # manifest_strict = False makes runtime {% static %} lookups fall back to
    # computing a hashed name when the manifest has no entry, instead of
    # raising. collectstatic still fails on references to files that do not
    # exist (the vendored jquery sourcemap reference is fixed by shipping the
    # map file), which is the desired strictness for deployments.
    manifest_strict = False


class StaticStorage(ManifestFilesMixin, S3Boto3Storage):
    # Served from the same per-association public bucket as media under the
    # 'static' prefix (set via STORAGES OPTIONS). Hashed filenames (manifest
    # storage) make CDN caching immutable. WhiteNoise's compressed storage is
    # intentionally not used here: its compression stage needs local
    # filesystem paths, which S3 does not provide.
    default_acl = 'public-read'
    # Vendored assets reference files that do not exist (jquery sourcemap);
    # fall back to the unhashed path instead of failing collectstatic.
    manifest_strict = False
    # How long a worker waits before re-attempting a failed manifest load.
    # Long-lived workers that boot before the release-time collectstatic
    # upload would otherwise fall back to an S3 HEAD+GET per {% static %}
    # tag for the whole process lifetime (~70 serial calls, ~2.3 s per page
    # render, measured on qa 2026-08-30). The retry gate bounds the slow
    # fallback to one interval after the upload appears.
    manifest_retry_interval = 60
    _manifest_retry_at = 0.0

    def __init__(self, *args, **kwargs):
        # The mixin loads the manifest during super().__init__(), so the lock
        # must exist before that. Sync Django views run in a threadpool under
        # the async gunicorn worker, so manifest reloads must be serialized.
        self._manifest_lock = threading.RLock()
        super().__init__(*args, **kwargs)
        # S3Boto3Storage.url() prepends the protocol, so the domain must be
        # scheme-less; accept the scheme'd form the codebase uses elsewhere.
        if self.custom_domain and "//" in self.custom_domain:
            self.custom_domain = self.custom_domain.split("//", 1)[1]

    def load_manifest(self):
        # The manifest lives in S3 (uploaded by the release-time collectstatic).
        # Tolerate missing/transient states: while the manifest is unavailable,
        # return the (empty) loaded state cheaply and only re-attempt the load
        # once per retry interval, so a worker that booted before the upload
        # self-heals instead of hitting S3 for every {% static %} lookup.
        if time.monotonic() < self._manifest_retry_at:
            return getattr(self, "hashed_files", {}), getattr(self, "manifest_hash", "")
        with self._manifest_lock:
            # Double-checked: another thread may have reloaded while waiting.
            if time.monotonic() < self._manifest_retry_at:
                return self.hashed_files, self.manifest_hash
            try:
                paths, manifest_hash = super().load_manifest()
            except Exception as exc:
                logger.warning(
                    "Static manifest load failed (%s); retrying in %ss",
                    exc,
                    self.manifest_retry_interval,
                )
                paths, manifest_hash = {}, ""
            if paths:
                self._manifest_retry_at = 0.0
                self.hashed_files, self.manifest_hash = paths, manifest_hash
            else:
                self._manifest_retry_at = time.monotonic() + self.manifest_retry_interval
                # Also surfaces permanent deployment errors (misconfigured
                # storage, missing manifest object) at most once per retry
                # interval, so self-healing failures are observable.
                logger.warning(
                    "Static manifest not available; static lookups fall back to "
                    "S3 per tag until it appears (retry in %ss)",
                    self.manifest_retry_interval,
                )
            return paths, manifest_hash

    def stored_name(self, name):
        # The manifest mixin only loads once at construction; when it came up
        # empty (upload not finished yet), retry periodically so the worker
        # picks up the manifest without a restart.
        if not self.hashed_files and time.monotonic() >= self._manifest_retry_at:
            with self._manifest_lock:
                if not self.hashed_files and time.monotonic() >= self._manifest_retry_at:
                    self.hashed_files, self.manifest_hash = self.load_manifest()
        return super().stored_name(name)


class PrivateMediaStorage(S3Boto3Storage):
    bucket_name = getattr(settings, 'AWS_PRIVATE_STORAGE_BUCKET_NAME', settings.AWS_STORAGE_BUCKET_NAME)  # type: ignore[misc]
    location = settings.PRIVATE_MEDIA_LOCATION  # type: ignore[misc]
    default_acl = 'private'
    file_overwrite = False
    custom_domain = getattr(settings, 'AWS_S3_PRIVATE_CUSTOM_DOMAIN', None)

    def url(self, name, parameters=None, expire=None, http_method=None):
        # django-storages returns unsigned URLs when custom_domain is set;
        # private files must stay presigned. Generate the presigned URL against
        # the endpoint host, then swap only the host for the custom domain. The
        # Worker rewrites the Host header to the S3 endpoint host (the hostname
        # the URL was signed against) and forwards path + query unchanged, so
        # the SigV4 signature still validates.
        if not self.custom_domain:
            return super().url(name, parameters=parameters, expire=expire, http_method=http_method)

        name = self._normalize_name(clean_name(name))
        params = parameters.copy() if parameters else {}
        params["Bucket"] = self.bucket.name
        params["Key"] = name

        connection = self.connection if self.querystring_auth else self.unsigned_connection
        url = connection.meta.client.generate_presigned_url(
            "get_object",
            Params=params,
            ExpiresIn=self.querystring_expire if expire is None else expire,
            HttpMethod=http_method,
        )

        parts = urlsplit(url)
        host = self.custom_domain
        if "//" in host:
            host = host.split("//", 1)[1]
        return urlunsplit((parts.scheme, host.rstrip("/"), parts.path, parts.query, parts.fragment))


class PublicMediaStorage(S3Boto3Storage):
    bucket_name = getattr(settings, 'AWS_PUBLIC_STORAGE_BUCKET_NAME', settings.AWS_STORAGE_BUCKET_NAME)  # type: ignore[misc]
    location = settings.PUBLIC_MEDIA_LOCATION  # type: ignore[misc]
    default_acl = 'public-read'
    file_overwrite = False
    querystring_auth = False
    custom_domain = getattr(settings, 'AWS_S3_PUBLIC_CUSTOM_DOMAIN', None)


class PublicCKEditorStorage(PublicMediaStorage):
    location = settings.PUBLIC_MEDIA_LOCATION + '/ckeditor'  # type: ignore[misc]
