import logging
import os
from io import BytesIO

from celery import shared_task
from django.core.files.base import ContentFile
from PIL import Image

from archive.models import Picture
from archive.uploads import delete_temp_upload_object, fetch_temp_upload_object, uploads_use_s3


logger = logging.getLogger("date")


def _open_picture_source(picture):
    if picture.temp_upload_key and uploads_use_s3():
        return BytesIO(fetch_temp_upload_object(picture.temp_upload_key))
    picture.image.open("rb")
    return picture.image


@shared_task
def optimize_picture_image(picture_id: int) -> None:
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
    except Exception as exc:
        logger.error("Failed opening picture %s for optimization: %s", picture_id, exc)
        picture.processing_status = Picture.PROCESSING_STATUS_FAILED
        picture.save(update_fields=["processing_status"])
        return

    try:
        image = image.convert("RGB")
        basewidth = 1600
        if image.size[0] > basewidth:
            width_ratio = basewidth / float(image.size[0])
            target_height = int(float(image.size[1]) * width_ratio)
            image = image.resize((basewidth, target_height), Image.LANCZOS)

        output = BytesIO()
        image.save(output, format="WEBP", quality=70, method=6)
        output.seek(0)

        original_name = os.path.basename(temporary_name or picture.original_filename or f"picture-{picture.pk}")
        stem, _ext = os.path.splitext(original_name)
        new_name = f"{stem}.webp"

        picture._skip_compression = True
        picture.image.save(new_name, ContentFile(output.read()), save=False)
        picture.original_filename = picture.original_filename or original_name
        picture.processing_status = Picture.PROCESSING_STATUS_READY
        picture.temp_upload_key = ""
        picture.save(update_fields=["image", "original_filename", "processing_status", "temp_upload_key"])
        if temporary_name and temporary_name != picture.image.name:
            picture.image.storage.delete(temporary_name)
        if uploads_use_s3() and temp_upload_key:
            delete_temp_upload_object(temp_upload_key)
    except Exception as exc:
        logger.error("Failed optimizing picture %s: %s", picture_id, exc)
        picture.processing_status = Picture.PROCESSING_STATUS_FAILED
        picture.save(update_fields=["processing_status"])
    finally:
        try:
            picture.image.close()
        except Exception:
            pass
        try:
            source_file.close()
        except Exception:
            pass
