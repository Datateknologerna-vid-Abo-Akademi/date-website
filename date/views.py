import datetime

from django.shortcuts import render, redirect
from django.template import RequestContext
from django.utils import translation

from django.conf import settings
from events.models import Event
from news.models import Post
from ads.models import AdUrl

from itertools import chain


def index(request):
    events = Event.objects.filter(published=True, event_date_end__gte=datetime.date.today()).order_by('event_date_start')
    news = Post.objects.filter(published=True).reverse()[:2]
    news_events = list(chain(events, news))

    ads = AdUrl.objects.all()

    return render(request, 'date/start.html', {'news_events': news_events, 'events': events, 'news': news, 'ads': ads})


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


def handler404(request, *args, **argv):
    response = render(request, '404.html', {})
    response.status_code = 404
    return response


def handler500(request, *args, **argv):
    response = render(request, '500.html', {})
    response.status_code = 404
    return response
