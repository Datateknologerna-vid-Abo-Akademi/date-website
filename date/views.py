import datetime
from itertools import chain

from django.conf import settings
from django.shortcuts import redirect, render
from django.utils import timezone
from django.utils import translation
from django.utils import timezone
from django.http import HttpResponse

from ads.models import AdUrl
from events.models import Event
from news.models import Post
from social.models import IgUrl


def index(request):
    events_old_events_included = (Event.objects.filter(
        published=True,
        event_date_end__gte=(timezone.now() - timezone.timedelta(days=31))).order_by('event_date_start'))
    events = events_old_events_included.filter(
        published=True, event_date_end__gte=timezone.now())
    news = Post.objects.filter(
        published=True, category__isnull=True).reverse()[:3]

    # Show Albins Angels logo if new post in last 10 days
    aa_posts = Post.objects.filter(published=True, category__name="Albins Angels").order_by(
        'published_time').reverse()[:1]  # TODO Remove this hardcoding or move to different function/file
    time_since = timezone.now() - timezone.timedelta(days=10)
    aa_post = ''
    if aa_posts and aa_posts[0].published_time > time_since:
        aa_post = aa_posts[0]

    def calendar_format(all_events):
        """ Format events into a dictionary where keys (dates)
        are mapped to data used by the calendar on the frontend"""
        calendar_events_dict = {}
        for event in all_events:
            event_url = "events/" + event.slug
            # The rest of the "html" field is set on the client side
            # since it includes a time that gets localized on the client-side
            event_dict = {event.event_date_start.strftime("%Y-%m-%d"):
                          {
                "link": event_url,
                "modifier": "calendar-eventday",
                "eventFullDate": event.event_date_start,
                "eventTitle": event.title,
                "html": f"<a class='calendar-eventday-popup' id='calendar_link' href='{event_url}'>"
            }
            }
            calendar_events_dict.update(event_dict)
        return calendar_events_dict

    context = {
        'calendar_events': calendar_format(events_old_events_included),
        'events': events,
        'news': news,
        'news_events': list(chain(events, news)),
        'ads': AdUrl.objects.all(),
        'posts': IgUrl.objects.all(),
        'aa_post': aa_post,  # TODO Remove or rename
    }

    return render(request, 'date/start.html', context)


def set_language(request):
    user_language = request.POST.get("lang")

    # persist the language preference using a cookie
    translation.activate(user_language)
    origin = request.META.get('HTTP_REFERER')
    response = redirect(origin)
    response.set_cookie(settings.LANGUAGE_COOKIE_NAME, user_language)
    return response


def handler404(request, *args, **argv):
    response = render(request, 'core/404.html', {})
    response.status_code = 404
    return response


def handler500(request, *args, **argv):
    response = render(request, 'core/500.html', {})
    response.status_code = 404
    return response
