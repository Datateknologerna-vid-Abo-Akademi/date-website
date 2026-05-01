import sys
import os
import django
from django.utils.timezone import now


sys.path.append("/code")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings.date")
django.setup()

from events.models import EventAttendees, Event

source_index = sys.argv[1]
target_index = sys.argv[2]

source_event = Event.objects.filter(id=source_index).first()
target_event = Event.objects.filter(id=target_index).first()
storage_event = target_event.parent or target_event

source_participants = EventAttendees.objects.filter(event=source_event.id).all()

for participant in source_participants:
    if EventAttendees.objects.filter(event=storage_event, email=participant.email).exists():
        continue

    avec_for = None
    if participant.avec_for:
        avec_for = EventAttendees.objects.filter(
            event=storage_event, email=participant.avec_for.email
        ).first()

    EventAttendees.objects.create(
        user=participant.user,
        email=participant.email,
        anonymous=participant.anonymous,
        preferences=participant.preferences,
        time_registered=now(),
        event=storage_event,
        original_event=target_event,
        avec_for=avec_for,
    )
