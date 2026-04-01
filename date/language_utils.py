from django.conf import settings
from django.utils.translation import get_supported_language_variant


def resolve_language(language_code):
    if not language_code:
        return settings.LANGUAGE_CODE

    try:
        return get_supported_language_variant(language_code)
    except LookupError:
        return settings.LANGUAGE_CODE
