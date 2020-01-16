from django.conf import settings
from django.utils import translation
from django.utils.deprecation import MiddlewareMixin


class LangMiddleware(MiddlewareMixin):

    @staticmethod
    def process_request(request):
        request.LANG = getattr(settings, 'LANGUAGE_CODE', settings.LANGUAGE_CODE)
        try:
            lang = request.session[translation.LANGUAGE_SESSION_KEY]
            if lang in [settings.LANG_SWEDISH, settings.LANG_FINNISH] and lang is not None:
                request.LANG = lang
        except KeyError:
            pass

        translation.activate(request.LANG)
        request.LANGUAGE_CODE = request.LANG
