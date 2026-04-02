from django.conf import settings
from django.http import HttpResponse
from django.shortcuts import render
from django.utils import translation
from django.utils.deprecation import MiddlewareMixin
from .language_utils import resolve_language


class LangMiddleware(MiddlewareMixin):
    @staticmethod
    def process_request(request):
        request._previous_language = translation.get_language()
        # Let Django's LocaleMiddleware resolve language from the URL first.
        request.LANG = resolve_language(
            getattr(request, "LANGUAGE_CODE", None)
            or request.COOKIES.get(settings.LANGUAGE_COOKIE_NAME, settings.LANGUAGE_CODE)
        )
        translation.activate(request.LANG)
        request.LANGUAGE_CODE = request.LANG

    @staticmethod
    def process_response(request, response):
        previous_language = getattr(request, "_previous_language", None)
        if previous_language:
            translation.activate(previous_language)
        else:
            translation.deactivate()
        return response


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
        self.cdn_url_transformations = getattr(settings, "CDN_URL_TRANSFORMATIONS", [])

    def __call__(self, request):
        response = self.get_response(request)

        if not getattr(response, "streaming", False):
            for original, new in self.cdn_url_transformations:
                if original and new:
                    response.content = response.content.replace(
                        bytes(original, "utf-8"), bytes(new, "utf-8")
                    )
        # Streaming responses do not expose a mutable `.content` buffer here.

        return response
