from django.conf import settings


def captcha_context(_):
    return {"CAPTCHA_SITE_KEY": settings.CAPTCHA_SITE_KEY}


def apply_content_variables(_):
    return settings.CONTENT_VARIABLES
