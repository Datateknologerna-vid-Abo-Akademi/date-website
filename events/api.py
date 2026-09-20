from django.conf import settings
from django.http import JsonResponse
from django.urls import reverse
from django.utils import timezone, translation
from django.views.decorators.cache import cache_control
from django.views.decorators.http import require_safe
from django.views.decorators.vary import vary_on_cookie

from .models import Event

UPCOMING_EVENTS_CACHE_SECONDS = 60
MAX_RESULTS = 200


def _serialize_event(request, event):
    return {
        "id": event.pk,
        "title": event.title,
        "slug": event.slug,
        "url": request.build_absolute_uri(reverse('events:detail', args=[event.slug])),
        "event_date_start": event.event_date_start.isoformat(),
        "event_date_end": event.event_date_end.isoformat(),
        "content": event.content,
        "image": request.build_absolute_uri(event.background_image_url) if event.background_image_url else "",
        "redirect_link": event.redirect_link,
    }


def _resolve_language(request):
    requested = request.GET.get('lang')
    if requested and requested in dict(settings.LANGUAGES):
        return requested
    return translation.get_language()


@require_safe
@cache_control(public=True, max_age=UPCOMING_EVENTS_CACHE_SECONDS)
@vary_on_cookie
def upcoming_events(request):
    """Public JSON list of upcoming, published events open to anyone.

    Members-only and passcode-protected events are excluded: anonymous
    visitors cannot view those detail pages at all (see
    EventDetailView._requires_member_login and the passcode gate in
    EventDetailView.get/handle_passcode), so they are left out of this
    public listing too. `content` is raw CKEditor HTML, unlike the .ics
    feed which strips tags.

    Language: `title`/`content` follow the site's cookie-based language
    (Accept-Language is ignored everywhere on this site), or an explicit
    `?lang=` query parameter validated against `settings.LANGUAGES`, for
    clients that cannot carry a cookie.
    """
    now = timezone.now()
    events = (
        Event.objects.published()
        .filter(event_date_end__gte=now, members_only=False, passcode="")
        .exclude(slug="")
        .exclude(slug__isnull=True)
        .order_by('event_date_start', 'id')[:MAX_RESULTS]
    )
    with translation.override(_resolve_language(request)):
        data = [_serialize_event(request, event) for event in events]
    return JsonResponse({"events": data})
