import logging
from smtplib import SMTPException

import requests
from celery import shared_task
from django.conf import settings
from django.core.mail import EmailMultiAlternatives, send_mail
from django.db import transaction

logger = logging.getLogger("date")

VALIDATION_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"


def validate_captcha(response: str) -> bool:
    secret_key = settings.TURNSTILE_SECRET_KEY  # type: ignore[misc]
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
        res = requests.post(VALIDATION_URL, data=data, timeout=5)
    except Exception:
        logger.info("Request to cloudflare failed")
        return False

    return res.json().get('success', False)


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


@shared_task
def send_email_with_attachments_task(
    subject: str,
    body: str,
    from_email: str,
    to: list[str],
    *,
    html_message: str | None = None,
    attachments: tuple = (),
) -> None:
    """Like send_email_task, for a message that carries files.

    send_mail has no way to attach anything, so this builds the message itself.
    The failure handling matches send_email_task: a mail problem is logged rather
    than raised, because the row this describes is already saved and a bounce
    must not be reported to the user as a failed booking.
    """
    try:
        message = EmailMultiAlternatives(subject, body, from_email, to)
        if html_message:
            message.attach_alternative(html_message, "text/html")
        for filename, content, mimetype in attachments:
            message.attach(filename, content, mimetype)
        message.send()
    except SMTPException:
        logger.error(f"Failed sending email to: {to}")
    except Exception as e:
        logger.error(f"Unexpected error sending email: {e}")
