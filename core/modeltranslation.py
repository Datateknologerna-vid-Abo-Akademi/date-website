from django.conf import settings


def get_translation_languages() -> tuple[str, ...]:
    """Return the active site language codes for modeltranslation admin UI."""
    configured_languages = getattr(settings, "LANGUAGES", ())
    if configured_languages:
        return tuple(code for code, _label in configured_languages)
    return tuple(getattr(settings, "MODELTRANSLATION_LANGUAGES", ()))
