import datetime

from django.conf import settings
from django.shortcuts import redirect, render
from django.utils import translation
from django.utils import timezone
from django.views.decorators.cache import cache_page

from events.models import Event
from news.models import Post
from itertools import chain
from event_calendar.views import CalendarManager
from ads.models import AdUrl
from social.models import IgUrl


@cache_page(300)  # Cache page for 5 minutes
def index(request):
    cm = CalendarManager(request)
    d = cm.date

    events = Event.objects.filter(published=True, event_date_end__gte=d).order_by(
        'event_date_start')
    news = Post.objects.filter(published=True, albins_angels=False).reverse()[:2]

    # Show Albins Angels logo if new post in last 10 days
    aa_posts = Post.objects.filter(published=True, albins_angels=True).order_by('published_time').reverse()[:1]
    time_since = timezone.now() - datetime.timedelta(days=10)
    aa_post = ''
    if aa_posts and aa_posts[0].published_time > time_since:
        aa_post = aa_posts[0]



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
