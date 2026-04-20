import logging
import os
from io import BytesIO

from celery import shared_task
from django.core.files.base import ContentFile
from PIL import Image

from archive.models import Picture
from archive.uploads import delete_temp_upload_object, fetch_temp_upload_object, uploads_use_s3
from core.utils import resize_and_encode_webp


logger = logging.getLogger("date")


def _open_picture_source(picture):
    if picture.temp_upload_key and uploads_use_s3():
        return BytesIO(fetch_temp_upload_object(picture.temp_upload_key))
    picture.image.open("rb")
    return picture.image


@shared_task(bind=True, autoretry_for=(Exception,), max_retries=3, default_retry_delay=60)
def optimize_picture_image(self, picture_id: int) -> None:
    try:
        picture = Picture.objects.get(pk=picture_id)
    except Picture.DoesNotExist:
        logger.warning("Picture %s disappeared before optimization ran.", picture_id)
        return

    if picture.processing_status == Picture.PROCESSING_STATUS_READY:
        return

    temporary_name = picture.image.name if picture.image else ""
    temp_upload_key = picture.temp_upload_key
    source_file = None
    picture.processing_status = Picture.PROCESSING_STATUS_PROCESSING
    picture.save(update_fields=["processing_status"])

    try:
        source_file = _open_picture_source(picture)
        image = Image.open(source_file)
        image.load()

        output = resize_and_encode_webp(image, max_width=1600, quality=70)

        original_name = os.path.basename(temporary_name or picture.original_filename or f"picture-{picture.pk}")
        stem, _ext = os.path.splitext(original_name)
        new_name = f"{stem}.webp"

        picture._skip_compression = True
        picture.image.save(new_name, ContentFile(output.read()), save=False)
        picture.original_filename = picture.original_filename or original_name
        picture.processing_status = Picture.PROCESSING_STATUS_READY
        picture.temp_upload_key = None
        picture.save(update_fields=["image", "original_filename", "processing_status", "temp_upload_key"])
        if temporary_name and temporary_name != picture.image.name:
            picture.image.storage.delete(temporary_name)
    except Exception as exc:
        logger.error("Failed optimizing picture %s: %s", picture_id, exc)
        if self.request.retries >= self.max_retries:
            picture.processing_status = Picture.PROCESSING_STATUS_FAILED
            picture.save(update_fields=["processing_status"])
        raise
    finally:
        try:
            picture.image.close()
        except Exception:
            pass
        try:
            if source_file:
                source_file.close()
        except Exception:
            pass

    if uploads_use_s3() and temp_upload_key:
        try:
            delete_temp_upload_object(temp_upload_key)
        except Exception as exc:
            logger.warning("Failed to delete temp upload object %s: %s", temp_upload_key, exc)
