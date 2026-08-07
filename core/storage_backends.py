from urllib.parse import urlsplit, urlunsplit

from django.conf import settings
from storages.backends.s3boto3 import S3Boto3Storage
from storages.utils import clean_name


class StaticStorage(S3Boto3Storage):
    location = 'static'
    default_acl = 'public-read'


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

        connection = (
            self.connection if self.querystring_auth else self.unsigned_connection
        )
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
