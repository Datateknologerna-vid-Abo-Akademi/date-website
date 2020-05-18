import datetime

from django.shortcuts import render, redirect
from django.utils import translation

from django.conf import settings
from events.models import Event
from news.models import Post
from ads.models import AdUrl, IgUrl
from itertools import chain
from event_calendar.views import get_calendar, get_date, prev_month, next_month


def index(request):
    d = get_date(request.GET.get('month', None))

    events = Event.objects.filter(published=True, event_date_end__gte=d).order_by(
        'event_date_start')
    news = Post.objects.filter(published=True).reverse()[:2]
    context = {
        'events': events,
        'news': news,
        'news_events': list(chain(events, news)),
        'ads': AdUrl.objects.all(),
        'posts': IgUrl.objects.all(),
        'calendar': get_calendar(request),
        'prev_month': prev_month(d),
        'next_month': next_month(d),
    }

    return render(request, 'date/start.html', context)


def language(request, lang):
    if str(lang).lower() == 'fi':
        lang = settings.LANG_FINNISH
    else:
        lang = settings.LANG_SWEDISH
    translation.activate(lang)
    request.session[translation.LANGUAGE_SESSION_KEY] = lang
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
