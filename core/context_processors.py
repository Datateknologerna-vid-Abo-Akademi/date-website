from django.conf import settings


def captcha_context(_):
    return {"CAPTCHA_SITE_KEY": settings.CAPTCHA_SITE_KEY}


def apply_content_variables(_):
    content_variables = settings.CONTENT_VARIABLES
    return {
        **content_variables,
        "EVENT_TEMPLATE_LOGO": content_variables.get(
            "EVENT_TEMPLATE_LOGO",
            content_variables.get("ASSOCIATION_LOGO", "core/images/headerlogo.png"),
        ),
        "ENABLE_LANGUAGE_FEATURES": settings.ENABLE_LANGUAGE_FEATURES,
        "MEMBERS_SIGNUP_ENABLED": getattr(settings, "MEMBERS_SIGNUP_ENABLED", True),
        "GITHUB_CLIENT_ID": getattr(settings, "GITHUB_CLIENT_ID", ""),
    }
