import logging
import requests

from django.conf import settings

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