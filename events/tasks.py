from celery import shared_task
from django.conf import settings
from django.template.loader import render_to_string

from core.utils import send_email_task
from .models import EventAttendees


@shared_task
def send_edit_token_email(attendee_id: int) -> None:
    attendee = EventAttendees.objects.get(id=attendee_id)
    context = {
        'TOKEN': attendee.edit_token,
        'SITE_URL': settings.CONTENT_VARIABLES.get('SITE_URL', 'https://datateknologerna.org'),
        'EVENT_TITLE': attendee.event.title,
    }
    message = render_to_string('events/edit_signup_email.txt', context)
    subject = f"Uppdatera din anm\xe4lan till {attendee.event.title}"
    send_email_task.delay(subject, message, settings.DEFAULT_FROM_EMAIL, [attendee.email])
