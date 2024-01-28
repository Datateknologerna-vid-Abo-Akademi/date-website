import datetime
import random

from django.conf import settings
from django.shortcuts import redirect, render
from django.utils import translation
from itertools import chain

from ads.models import AdUrl
from events.models import Event
from news.models import Post
from social.models import IgUrl


def index(request):
    events = Event.objects.filter(published=True, event_date_end__gte=datetime.datetime.now()).order_by(
        'event_date_start')
    news = Post.objects.filter(published=True).reverse()[:2]

    def calendar_format(x):
        formatstr = "%H:%M"
        calendar_events_dict = {}
        for e in x:
            event_url = "events/" + e.slug
            event_dict = {e.event_date_start.strftime("%Y-%m-%d") :
                {
                "link": event_url,
                "modifier": "calendar-eventday",
                 "html": f"<a class='calendar-eventday-popup' id='calendar_link' href='{event_url}'> {e.event_date_start.strftime(formatstr)}<br>{e.title}</a>"
                 }
                }
            calendar_events_dict.update(event_dict)
        return calendar_events_dict

    context = {
            'calendar_events' : calendar_format(events),
            'events': events,
            'news': news,
            'news_events': list(chain(events, news)),
            'ads': AdUrl.objects.all(),
            'posts': IgUrl.objects.all(), #'calendar': cm.get_calendar(),
            }

    # KK april fools frontpage
    date = datetime.date(1337, 4, 1)
    date_of_today = datetime.date.today()
    if date.month == date_of_today.month and date.day == date_of_today.day and random.randint(1, 4) == 1:
        return render(request, 'date/april_start.html', context)
    return render(request, 'date/start.html', context)


def language(request, lang):
    if str(lang).lower() == 'fi':
        lang = settings.LANG_FINNISH
    else:
        lang = settings.LANG_SWEDISH
    translation.activate(lang)
    # TODO Replace LANGUAGE_SESSION_KEY with something that works in django 4.0
    # request.session[translation.LANGUAGE_SESSION_KEY] = lang
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
