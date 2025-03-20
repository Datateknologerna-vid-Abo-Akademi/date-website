from django.conf import settings


def captcha_context(_):
    return {"CAPTCHA_SITE_KEY": settings.CAPTCHA_SITE_KEY}


def apply_content_variables(_):
    return settings.CONTENT_VARIABLES


def cookie_consent(request):
    """Check if the user has accepted cookies and pass the info to templates."""
    consent_value = request.COOKIES.get("cookie_consent", "false")
    return {"cookie_consent": consent_value}
