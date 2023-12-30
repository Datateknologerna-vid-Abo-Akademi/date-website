import logging
from smtplib import SMTPException

import requests
from celery import shared_task
from django.conf import settings
from django.core.mail import send_mail

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


@shared_task
def send_email_task(*args, **kwargs) -> None:
    try:
        send_mail(*args, **kwargs)
    except SMTPException:
        print(f"Failed sending email to: {args[3] or kwargs.get('to', '')}")
