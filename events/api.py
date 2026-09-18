from django.http import JsonResponse
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.cache import cache_control
from django.views.decorators.http import require_GET

from .models import Event

UPCOMING_EVENTS_CACHE_SECONDS = 60


def _serialize_event(request, event):
    return {
        "id": event.pk,
        "title": event.title,
        "slug": event.slug,
        "url": request.build_absolute_uri(reverse('events:detail', args=[event.slug])),
        "event_date_start": event.event_date_start.isoformat(),
        "event_date_end": event.event_date_end.isoformat(),
        "content": event.content,
        "image": event.background_image_url,
    }


@require_GET
@cache_control(public=True, max_age=UPCOMING_EVENTS_CACHE_SECONDS)
def upcoming_events(request):
    """Public JSON list of upcoming, published, non-members-only events.

    Members-only events are excluded: anonymous visitors cannot view their
    detail page (see EventDetailView._requires_member_login), so they are
    left out of this public listing too.
    """
    now = timezone.now()
    events = (
        Event.objects.published()
        .filter(event_date_end__gte=now, members_only=False)
        .exclude(slug="")
        .exclude(slug__isnull=True)
        .order_by('event_date_start')
    )
    return JsonResponse({"events": [_serialize_event(request, event) for event in events]})
