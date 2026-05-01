import re

from django.conf import settings
from django.http import HttpResponse
from django.shortcuts import render
from django.utils import translation
from django.utils.deprecation import MiddlewareMixin
from django.utils.translation import get_language_from_request
from .language_utils import resolve_language


class LanguageStateMiddleware(MiddlewareMixin):
    @staticmethod
    def process_request(request):
        request._previous_language = translation.get_language()

    @staticmethod
    def process_response(request, response):
        previous_language = getattr(request, "_previous_language", None)
        if previous_language:
            translation.activate(previous_language)
        else:
            translation.deactivate()
        return response


class LangMiddleware(MiddlewareMixin):
    @staticmethod
    def process_request(request):
        # No URL-based language prefixes. Browser language detection is opt-in
        # so first visits start from LANGUAGE_CODE unless a cookie is present.
        if getattr(settings, "USE_ACCEPT_LANGUAGE_HEADER", False):
            lang = get_language_from_request(request, check_path=False)
        else:
            lang = request.COOKIES.get(settings.LANGUAGE_COOKIE_NAME)
        request.LANG = resolve_language(lang)
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

    URL_BYTES_PATTERN = rb'[^"\'\s<>()]+'
    PRESIGNED_S3_MARKERS = (b"X-Amz-Algorithm=", b"X-Amz-Signature=")

    def __init__(self, get_response):
        self.get_response = get_response
        self.cdn_url_transformations = getattr(settings, "CDN_URL_TRANSFORMATIONS", [])
        self._cdn_patterns = []
        for original, new in self.cdn_url_transformations:
            if original and new:
                self._cdn_patterns.append(
                    (
                        original.encode("utf-8"),
                        new.encode("utf-8"),
                        re.compile(re.escape(original.encode("utf-8")) + self.URL_BYTES_PATTERN),
                    )
                )

    def __call__(self, request):
        response = self.get_response(request)

        if not getattr(response, "streaming", False):
            for original, new, pattern in self._cdn_patterns:
                # Keep presigned private-media URLs on their original host, since
                # their signatures cover the request host and break if rewritten.
                response.content = pattern.sub(
                    lambda match: match.group(0)
                    if any(marker in match.group(0) for marker in self.PRESIGNED_S3_MARKERS)
                    else match.group(0).replace(original, new, 1),
                    response.content,
                )
        # Streaming responses do not expose a mutable `.content` buffer here.

        return response
