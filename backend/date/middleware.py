import logging

from django.conf import settings
from django.shortcuts import render
from django.utils import translation
from django.utils.deprecation import MiddlewareMixin

logger = logging.getLogger("date")


def _normalize_host(raw_host: str) -> str:
    if not raw_host:
        return ""
    host = raw_host.strip().lower()
    return host.split(":", 1)[0]


def _pick_locale_from_accept_language(raw_header: str):
    if not raw_header:
        return None
    for part in raw_header.split(","):
        value = part.split(";", 1)[0].strip().lower()
        if not value:
            continue
        base = value.split("-", 1)[0]
        if base:
            return base
    return None


def _get_supported_locales():
    configured = getattr(settings, "SUPPORTED_API_LOCALES", None)
    if configured:
        return set(configured)

    languages = getattr(settings, "LANGUAGES", [])
    if languages:
        return {code for code, _label in languages if code}

    return {getattr(settings, "LANGUAGE_CODE", "sv")}


class TenantContextMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        self.trust_forwarded_host = bool(getattr(settings, "TRUST_X_FORWARDED_HOST", True))
        self.allow_direct_host_fallback = bool(
            getattr(settings, "ALLOW_DIRECT_HOST_TENANT_FALLBACK", settings.DEBUG)
        )
        self.tenant_host_map = getattr(settings, "TENANT_HOST_MAP", {})

    def __call__(self, request):
        forwarded_host = request.META.get("HTTP_X_FORWARDED_HOST", "")
        host_header = request.META.get("HTTP_HOST", "")
        resolved_host = ""
        source = "default"

        if self.trust_forwarded_host and forwarded_host:
            resolved_host = _normalize_host(forwarded_host)
            source = "x-forwarded-host"
        elif self.allow_direct_host_fallback and host_header:
            resolved_host = _normalize_host(host_header)
            source = "host"

        resolved_tenant_slug = self.tenant_host_map.get(resolved_host, settings.PROJECT_NAME)
        request.tenant_slug = resolved_tenant_slug
        request.tenant_resolution_source = source
        request.tenant_resolution_host = resolved_host

        asserted_tenant = request.META.get("HTTP_X_TENANT_SLUG")
        if asserted_tenant and asserted_tenant != resolved_tenant_slug:
            logger.warning(
                "Tenant header mismatch: asserted=%s resolved=%s host=%s source=%s",
                asserted_tenant,
                resolved_tenant_slug,
                resolved_host,
                source,
            )

        response = self.get_response(request)
        response["X-Resolved-Tenant"] = resolved_tenant_slug
        response["Vary"] = ", ".join(
            sorted(
                {
                    *(value.strip() for value in response.get("Vary", "").split(",") if value.strip()),
                    "Host",
                    "X-Forwarded-Host",
                    "Accept-Language",
                }
            )
        )
        return response


class LocaleResolutionMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        self.supported_locales = _get_supported_locales()
        self.language_cookie_name = getattr(settings, "LANGUAGE_COOKIE_NAME", "django_language")
        self.tenant_default_locales = getattr(settings, "TENANT_DEFAULT_LOCALES", {})

    def __call__(self, request):
        resolved_locale = self._resolve_locale(request)
        request.resolved_locale = resolved_locale
        return self.get_response(request)

    def _resolve_locale(self, request):
        tenant_slug = getattr(request, "tenant_slug", settings.PROJECT_NAME)
        tenant_default = self.tenant_default_locales.get(tenant_slug, settings.LANGUAGE_CODE)
        explicit_locale = (request.META.get("HTTP_X_LOCALE") or "").lower().strip()
        cookie_locale = (request.COOKIES.get(self.language_cookie_name) or "").lower().strip()
        accept_language_locale = _pick_locale_from_accept_language(
            request.META.get("HTTP_ACCEPT_LANGUAGE", "")
        )

        candidates = [explicit_locale, cookie_locale, accept_language_locale, tenant_default]
        for candidate in candidates:
            if candidate and candidate in self.supported_locales:
                return candidate
        return settings.LANGUAGE_CODE


class LangMiddleware(MiddlewareMixin):

    @staticmethod
    def process_request(request):
        request.LANG = getattr(request, "resolved_locale", getattr(settings, "LANGUAGE_CODE", settings.LANGUAGE_CODE))
        try:
            pass
            # TODO This is borked as of Django 4.0 but it doesn't seem like it's in use
            # See: https://stackoverflow.com/questions/2605384/how-to-explicitly-set-django-language-in-django-session
            # lang = request.session[translation.LANGUAGE_SESSION_KEY]
            # if lang in [settings.LANG_SWEDISH, settings.LANG_FINNISH] and lang is not None:
            #    request.LANG = lang
        except KeyError:
            pass

        translation.activate(request.LANG)
        request.LANGUAGE_CODE = request.LANG


class HTCPCPMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        coffe_words = [f"/{x}" for x in ["coffee", "kahvi", "kaffe"]]
        htcpcp_methods = ["BREW", "POST", "BREW", "PROPFIND", "WHEN", "GET"]
        if request.path in coffe_words and request.method in htcpcp_methods:
            return render(request, template_name="core/418.html", status=418)
        return self.get_response(request)


class CDNRewriteMiddleware:
    """
    Middleware to rewrite URLs for static and media files to use a CDN if configured.
    """

    def __init__(self, get_response):
        self.get_response = get_response
        self.cdn_url_transformations = getattr(settings, 'CDN_URL_TRANSFORMATIONS', [])

    def __call__(self, request):
        response = self.get_response(request)

        for original, new in self.cdn_url_transformations:
            if original and new:
                response.content = response.content.replace(
                    bytes(original, 'utf-8'),
                    bytes(new, 'utf-8')
                )

        return response
