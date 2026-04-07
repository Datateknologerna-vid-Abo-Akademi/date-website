from storages.backends.s3boto3 import S3Boto3Storage
from django.conf import settings

# When S3_USE_ACL is False (e.g. Backblaze B2), per-object ACLs are not sent.
# Access control must then be configured at the bucket level in the provider console.
_use_acl = getattr(settings, 'S3_USE_ACL', True)


class StaticStorage(S3Boto3Storage):
    location = 'static'
    default_acl = 'public-read' if _use_acl else None


class PrivateMediaStorage(S3Boto3Storage):
    location = settings.PRIVATE_MEDIA_LOCATION
    default_acl = 'private' if _use_acl else None
    file_overwrite = False


class PublicMediaStorage(S3Boto3Storage):
    location = settings.PUBLIC_MEDIA_LOCATION
    default_acl = 'public-read' if _use_acl else None
    file_overwrite = False
    querystring_auth = False


class PublicCKEditorStorage(PublicMediaStorage):
    location = settings.PUBLIC_MEDIA_LOCATION + '/ckeditor'
