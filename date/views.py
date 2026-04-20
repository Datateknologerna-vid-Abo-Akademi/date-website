import datetime
import logging
import random
from urllib.parse import urlsplit, urlunsplit

from django.conf import settings
from django.core.cache import cache
from django.db import connection
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils import translation
from .language_utils import resolve_language, strip_language_prefix

from ads.models import AdUrl
from events.models import Event
from news.models import Post
from social.models import IgUrl


logger = logging.getLogger(__name__)


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
    if is_april_first and random.randrange(20) == 0:
        return 'date/april_start.html'

    return 'date/start.html'


def index(request):
    current_time = timezone.now()
    events_old_events_included = (
        Event.objects.filter(
            published=True,
            event_date_end__gte=(current_time - timezone.timedelta(days=31)),
        )
        .exclude(slug="")
        .exclude(slug__isnull=True)
        .order_by('event_date_start')
    )
    all_events = list(events_old_events_included)
    events = [
        event for event in all_events
        if event.event_date_end >= current_time
    ]
    news = list(Post.objects.filter(
        published=True, category__isnull=True).reverse()[:3])

    # Show Albins Angels logo if new post in last 10 days
    aa_post = None
    if settings.PROJECT_NAME in {"date", "pulterit"}:
        aa_post = (
            Post.objects
            .filter(published=True, category__name="Albins Angels")
            .select_related("category")
            .order_by('-published_time')
            .first()
        )  # TODO Remove this hardcoding or move to different function/file
        time_since = current_time - timezone.timedelta(days=10)
        if aa_post and aa_post.published_time <= time_since:
            aa_post = None

    def calendar_format(all_events):
        """ Format events into a dictionary where keys (dates)
        are mapped to data used by the calendar on the frontend"""
        calendar_events_dict = {}
        for event in all_events:
            event_url = reverse("events:detail", kwargs={"slug": event.slug})
            # The rest of the "html" field is set on the client side
            # since it includes a time that gets localized on the client-side
            event_dict = {event.event_date_start.strftime("%Y-%m-%d"):
                          {
                "link": event_url,
                "modifier": "calendar-eventday",
                "eventFullDate": event.event_date_start,
                "eventTitle": event.title,
            }
            }
            calendar_events_dict.update(event_dict)
        return calendar_events_dict

    context = {
        'calendar_events': calendar_format(all_events),
        'events': events,
        'news': news,
        'ads': list(AdUrl.objects.all()),
        'posts': list(IgUrl.objects.all()) if settings.PROJECT_NAME == "kk" else (),
        'aa_post': aa_post,  # TODO Remove or rename
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
        redirect_target = urlunsplit(
            ("", "", bare_path, parsed_origin.query, parsed_origin.fragment)
        )
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
