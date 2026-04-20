import os
import uuid
from functools import lru_cache

import boto3
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.utils.text import slugify


def uploads_use_s3():
    return bool(getattr(settings, "USE_S3", False))


def get_private_bucket_name():
    return getattr(settings, "AWS_PRIVATE_STORAGE_BUCKET_NAME", settings.AWS_STORAGE_BUCKET_NAME)


def get_temp_upload_prefix():
    return getattr(settings, "ARCHIVE_TEMP_UPLOAD_LOCATION", f"{settings.PRIVATE_MEDIA_LOCATION}/tmp/archive")


def build_temp_upload_key(collection, filename):
    _, extension = os.path.splitext(filename or "")
    safe_extension = extension.lower()[:16]
    safe_collection = slugify(collection.title) or "album"
    return f"{get_temp_upload_prefix()}/{collection.pub_date:%Y}/{safe_collection}/{uuid.uuid4().hex}{safe_extension}"


@lru_cache(maxsize=1)
def _create_s3_client():
    return boto3.client(
        "s3",
        endpoint_url=settings.AWS_S3_ENDPOINT_URL,
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        region_name=settings.AWS_S3_REGION_NAME or None,
    )


def get_s3_client():
    if not uploads_use_s3():
        raise ImproperlyConfigured("S3 uploads are not configured.")
    return _create_s3_client()


def create_presigned_temp_upload(collection, filename, content_type, max_file_size):
    temp_key = build_temp_upload_key(collection, filename)
    bucket_name = get_private_bucket_name()
    fields = {
        "Content-Type": content_type,
    }
    conditions = [
        {"bucket": bucket_name},
        {"key": temp_key},
        {"Content-Type": content_type},
        ["content-length-range", 1, max_file_size],
    ]
    post = get_s3_client().generate_presigned_post(
        Bucket=bucket_name,
        Key=temp_key,
        Fields=fields,
        Conditions=conditions,
        ExpiresIn=900,
    )
    return {
        "upload_url": post["url"],
        "fields": post["fields"],
        "temp_key": temp_key,
    }


def head_temp_upload_object(key):
    return get_s3_client().head_object(
        Bucket=get_private_bucket_name(),
        Key=key,
    )


def fetch_temp_upload_object(key):
    response = get_s3_client().get_object(
        Bucket=get_private_bucket_name(),
        Key=key,
    )
    return response["Body"].read()


def delete_temp_upload_object(key):
    get_s3_client().delete_object(
        Bucket=get_private_bucket_name(),
        Key=key,
    )
