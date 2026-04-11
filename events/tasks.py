import logging
import os
from io import BytesIO

from celery import shared_task
from django.core.files.base import ContentFile
from PIL import Image

from events.models import Event


logger = logging.getLogger("date")


@shared_task
def optimize_event_image(event_id: int) -> None:
    try:
        event = Event.objects.get(pk=event_id)
    except Event.DoesNotExist:
        logger.warning("Event %s disappeared before image optimization ran.", event_id)
        return

    if not event.image:
        return

    try:
        event.image.open("rb")
        image = Image.open(event.image)
        image.load()
    except Exception as exc:
        logger.error("Failed opening event image for event %s: %s", event_id, exc)
        return

    try:
        image = image.convert("RGB")
        max_width = 2000
        if image.size[0] > max_width:
            ratio = max_width / float(image.size[0])
            target_height = int(float(image.size[1]) * ratio)
            image = image.resize((max_width, target_height), Image.LANCZOS)

        output = BytesIO()
        image.save(output, format="WEBP", quality=72, method=6)
        output.seek(0)

        original_name = os.path.basename(event.image.name or f"event-{event.pk}")
        stem, _ext = os.path.splitext(original_name)
        new_name = f"{stem}.webp"

        event.image.save(new_name, ContentFile(output.read()), save=False)
        event.save(update_fields=["image"])
    except Exception as exc:
        logger.error("Failed optimizing event image for event %s: %s", event_id, exc)
    finally:
        try:
            event.image.close()
        except Exception:
            pass
