import logging
import secrets
import time
from urllib.parse import urlsplit, urlunsplit

from django.conf import settings
from django.core.cache import cache
from django.db import connection, transaction
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone, translation
from django.utils.translation import get_language

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
    if not settings.APRIL_HOMEPAGE_ENABLED:
        return 'date/start.html'

    today = timezone.localdate()
    is_april_first = today.month == 4 and today.day == 1
    if is_april_first and secrets.randbelow(20) == 0:
        return 'date/april_start.html'

    return 'date/start.html'


def get_recent_albins_angels_post(now=None):
    now = now or timezone.now()
    cutoff = now - timezone.timedelta(days=RECENT_ALBINS_ANGELS_DAYS)
    return (
        Post.objects.filter(
            category__name=ALBINS_ANGELS_CATEGORY_NAME,
            published_time__lte=now,
            published_time__gt=cutoff,
        )
        .select_related('category')
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


# The TTL is only a backstop: every Event/Post/AdUrl/IgUrl save or delete
# bumps HOMEPAGE_VERSION_KEY (see date/apps.py), so admin edits invalidate
# cached anonymous homepages immediately. Development uses the dummy cache,
# so caching is off there.
HOMEPAGE_CACHE_TTL = 300
HOMEPAGE_VERSION_KEY = f"homepage-version:{settings.PROJECT_NAME}"


def _homepage_version():
    version = cache.get(HOMEPAGE_VERSION_KEY)
    if version is not None:
        return version
    # Initialize atomically and without expiry, with a nanosecond-time value:
    # an evicted key must never restart at a generation whose cached entries
    # may still exist (second-granularity time would collide within the same
    # second), or stale homepages would be served again.
    cache.add(HOMEPAGE_VERSION_KEY, time.time_ns(), timeout=None)
    # Another process may have initialized a different value in the meantime.
    return cache.get(HOMEPAGE_VERSION_KEY) or 1


def bump_homepage_version(**kwargs):
    """Invalidate cached anonymous homepages after the transaction commits."""

    def _bump():
        try:
            cache.incr(HOMEPAGE_VERSION_KEY)
        except ValueError:
            # Evicted (or never set): start a fresh generation that cannot
            # collide with any still-live entry (see _homepage_version).
            cache.add(HOMEPAGE_VERSION_KEY, time.time_ns(), timeout=None)

    transaction.on_commit(_bump)


def _homepage_context(now=None):
    now = now or timezone.now()
    # Evaluate each queryset exactly once; derive upcoming events in Python.
    recent_events = list(
        Event.objects.published()
        .filter(event_date_end__gte=now - timezone.timedelta(days=31))
        .exclude(slug="")
        .exclude(slug__isnull=True)
        .order_by('event_date_start')
    )
    upcoming_events = [event for event in recent_events if event.event_date_end >= now]
    news = list(Post.objects.published().filter(category__isnull=True).reverse()[:3])

    return {
        'calendar_events': format_calendar_events(recent_events),
        'events': upcoming_events,
        'news': news,
        'ads': list(AdUrl.objects.all()),
        'posts': list(IgUrl.objects.all()),
        'aa_post': get_recent_albins_angels_post(now=now),
    }


def index(request):
    cache_key = None
    if not request.user.is_authenticated:
        cache_key = (
            f"homepage:{settings.PROJECT_NAME}:{get_language()}:"
            f"{getattr(settings, 'APRIL_HOMEPAGE_ENABLED', False)}:{_homepage_version()}"
        )
        cached = cache.get(cache_key)
        if cached is not None:
            return render(request, get_homepage_template_name(), cached)

    context = _homepage_context()
    if cache_key is not None:
        cache.set(cache_key, context, HOMEPAGE_CACHE_TTL)
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
