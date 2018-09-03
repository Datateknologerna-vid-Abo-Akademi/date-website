from django import http
from django.shortcuts import render, redirect
from django.utils import translation

from date import settings


def index(request):
    return render(request, 'start/start.html')


def language(request, lang):
    if str(lang).lower() == 'fi':
        lang = settings.LANG_FINNISH
    else:
        lang = settings.LANG_SWEDISH
    translation.activate(lang)
    request.session[translation.LANGUAGE_SESSION_KEY] = lang
    # response = http.HttpResponse()
    # response.set_cookie()
    origin = request.META.get('HTTP_REFERER')
    return redirect(origin)
