import logging
import os
from io import BytesIO

from celery import shared_task
from django.core.files.base import ContentFile
from PIL import Image

from archive.models import Picture


logger = logging.getLogger("date")


@shared_task
def optimize_picture_image(picture_id: int) -> None:
    try:
        picture = Picture.objects.get(pk=picture_id)
    except Picture.DoesNotExist:
        logger.warning("Picture %s disappeared before optimization ran.", picture_id)
        return

    if (
        picture.upload_provider != Picture.UPLOAD_PROVIDER_LOCAL
        or not picture.image
    ):
        return

    try:
        picture.image.open("rb")
        image = Image.open(picture.image)
        image.load()
    except Exception as exc:
        logger.error("Failed opening picture %s for optimization: %s", picture_id, exc)
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

        original_name = os.path.basename(picture.image.name or picture.original_filename or f"picture-{picture.pk}")
        stem, _ext = os.path.splitext(original_name)
        new_name = f"{stem}.webp"

        picture._skip_compression = True
        picture.image.save(new_name, ContentFile(output.read()), save=False)
        picture.original_filename = picture.original_filename or original_name
        picture.save(update_fields=["image", "original_filename"])
    except Exception as exc:
        logger.error("Failed optimizing picture %s: %s", picture_id, exc)
    finally:
        try:
            picture.image.close()
        except Exception:
            pass
