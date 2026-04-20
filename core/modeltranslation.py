from django.conf import settings


def get_translation_languages() -> tuple[str, ...]:
    """Return stable language codes used for modeltranslation fields."""
    configured_languages = getattr(settings, "MODELTRANSLATION_LANGUAGES", ())
    if configured_languages:
        return tuple(configured_languages)

    site_languages = getattr(settings, "LANGUAGES", ())
    return tuple(code for code, _label in site_languages)
