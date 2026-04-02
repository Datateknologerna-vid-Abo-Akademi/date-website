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
    if not url:
        return url

    if "://" in url or url.startswith(("#", "mailto:", "tel:", "javascript:")):
        return url

    normalized_url = url if url.startswith("/") else f"/{url}"
    target_language = resolve_language(language_code)
    source_language = get_language_from_path(normalized_url)

    if source_language:
        language_prefix = f"/{source_language}"
        remainder = normalized_url[len(language_prefix):] or "/"
    else:
        remainder = normalized_url

    if not remainder.startswith("/"):
        remainder = f"/{remainder}"

    return f"/{target_language}{remainder}"
