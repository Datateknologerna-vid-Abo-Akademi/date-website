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
        # No URL-based language prefixes. Associations can opt out of browser
        # language detection so first visits always start from LANGUAGE_CODE.
        if getattr(settings, "USE_ACCEPT_LANGUAGE_HEADER", True):
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
