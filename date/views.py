import logging
import secrets
from itertools import chain
from urllib.parse import urlsplit, urlunsplit

from django.conf import settings
from django.core.cache import cache
from django.db import connection
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone, translation

from ads.models import AdUrl
from events.models import Event
from instagram.models import IgUrl
from news.models import Post

from .language_utils import resolve_language, strip_language_prefix

logger = logging.getLogger(__name__)
ALBINS_ANGELS_CATEGORY_NAME = "Albins Angels"
RECENT_ALBINS_ANGELS_DAYS = 10


def should_check_cache_readiness():
    return settings.CACHES["default"]["BACKEND"] != "django.core.cache.backends.dummy.DummyCache"


def healthz(request):
    return JsonResponse({"status": "ok"})


def readyz(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")

        if should_check_cache_readiness():
            cache_key = "readiness_check"
            cache.set(cache_key, "ok", 10)
            if cache.get(cache_key) != "ok":
                return JsonResponse({"status": "unhealthy"}, status=503)
    except Exception:
        logger.exception("Readiness check failed")
        return JsonResponse({"status": "unhealthy"}, status=503)

    return JsonResponse({"status": "ok"})


def get_homepage_template_name():
    """Return the homepage template for the active association."""
    if settings.PROJECT_NAME != 'kk':
        return 'date/start.html'

    today = timezone.localdate()
    is_april_first = today.month == 4 and today.day == 1
    if is_april_first and secrets.randbelow(20) == 0:
        return 'date/april_start.html'

    return 'date/start.html'


def get_recent_albins_angels_post(now=None):
    cutoff = (now or timezone.now()) - timezone.timedelta(days=RECENT_ALBINS_ANGELS_DAYS)
    return (
        Post.objects.published()
        .filter(
            category__name=ALBINS_ANGELS_CATEGORY_NAME,
            published_time__gt=cutoff,
        )
        .order_by('-published_time')
        .first()
    )


def format_calendar_events(all_events):
    """Return event metadata keyed by YYYY-MM-DD for the front-end calendar."""
    calendar_events = {}
    for event in all_events:
        event_url = reverse("events:detail", kwargs={"slug": event.slug})
        calendar_events[event.event_date_start.strftime("%Y-%m-%d")] = {
            "link": event_url,
            "modifier": "calendar-eventday",
            "eventFullDate": event.event_date_start,
            "eventTitle": event.title,
        }
    return calendar_events


def index(request):
    events_old_events_included = (
        Event.objects.published()
        .filter(
            event_date_end__gte=(timezone.now() - timezone.timedelta(days=31)),
        )
        .exclude(slug="")
        .exclude(slug__isnull=True)
        .order_by('event_date_start')
    )
    events = events_old_events_included.filter(event_date_end__gte=timezone.now())
    news = Post.objects.published().filter(category__isnull=True).reverse()[:3]

    context = {
        'calendar_events': format_calendar_events(events_old_events_included),
        'events': events,
        'news': news,
        'news_events': list(chain(events, news)),
        'ads': AdUrl.objects.all(),
        'posts': IgUrl.objects.all(),
        'aa_post': get_recent_albins_angels_post(),
    }

    return render(request, get_homepage_template_name(), context)


def set_language(request):
    user_language = resolve_language(request.POST.get("lang"))

    # persist the language preference using a cookie
    translation.activate(user_language)
    origin = request.META.get('HTTP_REFERER')
    if origin:
        parsed_origin = urlsplit(origin)
        bare_path = strip_language_prefix(parsed_origin.path)
        redirect_target = urlunsplit(("", "", bare_path, parsed_origin.query, parsed_origin.fragment))
    else:
        redirect_target = reverse("index")

    response = redirect(redirect_target)
    response.set_cookie(settings.LANGUAGE_COOKIE_NAME, user_language)
    return response


def handler404(request, *args, **argv):
    response = render(request, 'core/404.html', {})
    response.status_code = 404
    return response


def handler500(request, *args, **argv):
    response = render(request, 'core/500.html', {})
    response.status_code = 500
    return response
