import logging
import os

from celery import shared_task
from django.core.files.base import ContentFile
from PIL import Image

from core.utils import resize_and_encode_webp
from events.models import Event


logger = logging.getLogger("date")


@shared_task(bind=True, autoretry_for=(Exception,), max_retries=3, default_retry_delay=60)
def optimize_event_image(self, event_id: int) -> None:
    try:
        event = Event.objects.get(pk=event_id)
    except Event.DoesNotExist:
        logger.warning("Event %s disappeared before image optimization ran.", event_id)
        return

    if event.s3_image:
        image_field = event.s3_image
        field_name = "s3_image"
    elif event.image:
        image_field = event.image
        field_name = "image"
    else:
        return

    try:
        image_field.open("rb")
        image = Image.open(image_field)
        image.load()

        output = resize_and_encode_webp(image, max_width=2000, quality=72)

        original_name = os.path.basename(image_field.name or f"event-{event.pk}")
        stem, _ext = os.path.splitext(original_name)
        new_name = f"{stem}.webp"

        image_field.save(new_name, ContentFile(output.read()), save=False)
        event.save(update_fields=[field_name])
    except Exception as exc:
        logger.error("Failed optimizing event image for event %s: %s", event_id, exc)
        raise
    finally:
        try:
            image_field.close()
        except Exception:
            pass
