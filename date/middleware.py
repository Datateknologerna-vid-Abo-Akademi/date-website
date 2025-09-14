from django.conf import settings
from django.http import HttpResponse
from django.shortcuts import render
from django.utils import translation
from django.utils.deprecation import MiddlewareMixin


class LangMiddleware(MiddlewareMixin):

    @staticmethod
    def process_request(request):
        request.LANG = getattr(settings, 'LANGUAGE_CODE', settings.LANGUAGE_CODE)
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


class CDNRewriteMiddleare:
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
