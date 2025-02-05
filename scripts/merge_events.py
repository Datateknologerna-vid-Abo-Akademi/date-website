import datetime
import sys
import os
import django
from django.core.files import File


sys.path.append("/code")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings.date")
django.setup()

from events.models import EventAttendees, Event

source_index = sys.argv[1]
target_index = sys.argv[2]

source_event = Event.objects.filter(id=source_index).first()
target_event = Event.objects.filter(id=target_index).first()

source_participants = EventAttendees.objects.filter(event=source_event.id).all()

for participant in source_participants:
    if participant.avec_for:
        target_event.add_event_attendance(
            user= participant.user,
            email=participant.email,
            anonymous=participant.email,
            preferences=participant.preferences,
            avec_for=EventAttendees.objects.filter(event=target_event.id,email=participant.avec_for.email)
        )
        continue
    target_event.add_event_attendance(
        user= participant.user,
        email=participant.email,
        anonymous=participant.email,
        preferences=participant.preferences
    )
    

