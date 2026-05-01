from django.conf import settings
from django.utils.translation import get_language_from_path, get_supported_language_variant


def resolve_language(language_code):
    if not language_code:
        return settings.LANGUAGE_CODE

    try:
        return get_supported_language_variant(language_code)
    except LookupError:
        return settings.LANGUAGE_CODE


def localize_url(url, language_code):
    return strip_language_prefix(url)


def strip_language_prefix(url):
    if not url:
        return url
    if "://" in url or url.startswith(("#", "mailto:", "tel:", "javascript:")):
        return url
    normalized = url if url.startswith("/") else f"/{url}"
    lang = get_language_from_path(normalized)
    if lang:
        remainder = normalized[len(f"/{lang}"):] or "/"
        if not remainder.startswith("/"):
            remainder = f"/{remainder}"
        return remainder
    return normalized
