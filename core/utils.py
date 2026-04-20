import logging
from io import BytesIO
from smtplib import SMTPException

import requests
from celery import shared_task
from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction
from PIL import Image

logger = logging.getLogger("date")

VALIDATION_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"


def validate_captcha(response: str) -> bool:
    secret_key = settings.TURNSTILE_SECRET_KEY
    if secret_key == "":
        logger.info("No captcha secret key defined")
        return True
    if response == "":
        logger.info("No captcha found in response")
        return False

    data = {
        'secret': secret_key,
        'response': response,
    }

    try:
        res = requests.post(VALIDATION_URL, data=data)
    except Exception:
        logger.info("Request to cloudflare failed")
        return False

    return res.json().get('success', False)


def resize_and_encode_webp(image: Image.Image, max_width: int, quality: int) -> BytesIO:
    image = image.convert("RGB")
    if image.size[0] > max_width:
        ratio = max_width / float(image.size[0])
        target_height = int(float(image.size[1]) * ratio)
        image = image.resize((max_width, target_height), Image.LANCZOS)
    output = BytesIO()
    image.save(output, format="WEBP", quality=quality, method=4)
    output.seek(0)
    return output


def enqueue_task_on_commit(task, *args, **kwargs) -> None:
    transaction.on_commit(lambda: task.delay(*args, **kwargs))


@shared_task
def send_email_task(*args, **kwargs) -> None:
    try:
        send_mail(*args, **kwargs)
    except SMTPException:
        logger.error(f"Failed sending email to: {args[3] or kwargs.get('to', '')}")
    except Exception as e:
        logger.error(f"Unexpected error sending email: {e}")
