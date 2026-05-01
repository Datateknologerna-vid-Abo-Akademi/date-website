from storages.backends.s3boto3 import S3Boto3Storage
from django.conf import settings


class StaticStorage(S3Boto3Storage):
    location = 'static'
    default_acl = 'public-read'


class PrivateMediaStorage(S3Boto3Storage):
    bucket_name = getattr(settings, 'AWS_PRIVATE_STORAGE_BUCKET_NAME', settings.AWS_STORAGE_BUCKET_NAME)
    location = settings.PRIVATE_MEDIA_LOCATION
    default_acl = 'private'
    file_overwrite = False


class PublicMediaStorage(S3Boto3Storage):
    bucket_name = getattr(settings, 'AWS_PUBLIC_STORAGE_BUCKET_NAME', settings.AWS_STORAGE_BUCKET_NAME)
    location = settings.PUBLIC_MEDIA_LOCATION
    default_acl = 'public-read'
    file_overwrite = False
    querystring_auth = False


class PublicCKEditorStorage(PublicMediaStorage):
    location = settings.PUBLIC_MEDIA_LOCATION + '/ckeditor'
