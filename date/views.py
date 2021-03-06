import datetime

from django.conf import settings
from django.shortcuts import redirect, render
from django.utils import translation

from events.models import Event
from news.models import Post
from itertools import chain
from event_calendar.views import CalendarManager
from ads.models import AdUrl
from social.models import IgUrl


def index(request):
    cm = CalendarManager(request)
    d = cm.date

    events = Event.objects.filter(published=True, event_date_end__gte=d).order_by(
        'event_date_start')
    news = Post.objects.filter(published=True).reverse()[:2]
    context = {
        'events': events,
        'news': news,
        'news_events': list(chain(events, news)),
        'ads': AdUrl.objects.all(),
        'posts': IgUrl.objects.all(),
        'calendar': cm.get_calendar(),
        'prev_month': cm.prev_month(),
        'next_month': cm.next_month(),
        'curr_month': cm.curr_month_as_string(),
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
