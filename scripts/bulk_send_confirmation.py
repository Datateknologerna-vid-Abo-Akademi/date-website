import time
import sys
import os
import django


sys.path.append("/code")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings.on")
django.setup()

from events.models import EventAttendees
from billing.handlers import handle_send_confirmation

event_id = sys.argv[1]
# batch number (optional) -- which 400-entry batch to process (0-indexed)
batch = int(sys.argv[2]) if len(sys.argv) > 2 else 0
PAGE_SIZE = 400

start = batch * PAGE_SIZE
end = start + PAGE_SIZE

# order by attendee number and select the requested batch slice
attendees = EventAttendees.objects.filter(event__id=event_id).order_by('attendee_nr')[start:end]

total_selected = attendees.count()
print(f"Sending confirmation emails to {total_selected} attendees (batch {batch}, entries {start}-{end-1}) of event {event_id}")

for attendee in attendees:
    handle_send_confirmation(attendee)
    time.sleep(2)
