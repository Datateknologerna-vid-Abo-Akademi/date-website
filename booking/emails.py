"""Email notifications for external bookings.

Only the person who booked without a website account gets a confirmation.
Bookings made by a member, and bookings without an email address, are silent.
"""

from django.conf import settings
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from core.utils import enqueue_task_on_commit, send_email_task


def notify_external_booker(booking):
    if not booking.is_external or not booking.booker_email:
        return
    start = timezone.localtime(booking.start)
    end = timezone.localtime(booking.end)
    context = {
        'booking': booking,
        'room': booking.room,
        'start': start.strftime('%d.%m.%Y %H:%M'),
        'end': end.strftime('%H:%M'),
        # An email body is rendered without a request, so the context processor
        # that exposes the association's address to templates does not run here.
        # The booker needs that address: the board is the only route to change
        # or cancel a booking.
        'ASSOCIATION_EMAIL': getattr(settings, 'CONTENT_VARIABLES', {}).get('ASSOCIATION_EMAIL', ''),
    }
    subject = _('Bokningsbekräftelse för %(room)s') % {'room': booking.room.name}
    body = render_to_string('booking/booking_confirmation_email.txt', context)
    enqueue_task_on_commit(
        send_email_task,
        subject,
        body,
        settings.DEFAULT_FROM_EMAIL,
        [booking.booker_email],
    )
