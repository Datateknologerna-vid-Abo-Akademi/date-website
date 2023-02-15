import datetime
from itertools import chain

from django.conf import settings
from django.shortcuts import redirect, render
from django.utils import timezone
from django.utils import translation

from ads.models import AdUrl
from events.models import Event
from news.models import Post
from social.models import IgUrl


def index(request):
    events = Event.objects.filter(published=True, event_date_end__gte=datetime.datetime.now()).order_by(
        'event_date_start')
    news = Post.objects.filter(published=True, albins_angels=False).reverse()[:3]

    # Show Albins Angels logo if new post in last 10 days
    aa_posts = Post.objects.filter(published=True, albins_angels=True).order_by('published_time').reverse()[:1]
    time_since = timezone.now() - datetime.timedelta(days=10)
    aa_post = ''
    if aa_posts and aa_posts[0].published_time > time_since:
        aa_post = aa_posts[0]

    def calendar_format(x):
        formatstr = "%H:%M"
        event_url = "events/" + x.slug
        return {x.event_date_start.strftime("%Y-%m-%d") :
                {
                "link": event_url,
                "modifier": "calendar-eventday",
                 "html": f"<a class='calendar-eventday-popup' id='calendar_link' href='{event_url}'> {x.event_date_start.strftime(formatstr)}<br>{x.title}</a>"
                 }
                }

    calendar_events_dict = {}
    for x in events:
        calendar_events_dict.update(calendar_format(x))

    context = {
            'calendar_events' : calendar_format(events),
            'events': events,
            'news': news,
            'news_events': list(chain(events, news)),
            'ads': AdUrl.objects.all(),
            'posts': IgUrl.objects.all(), #'calendar': cm.get_calendar(),
            'aa_post': aa_post,
            }

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
