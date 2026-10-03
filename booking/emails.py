"""Email notifications for bookings.

The person who booked is told either way, member or not. A member used to get
nothing, on the reasoning that the booking is visible in their account, but the
confirmation and the calendar invite are worth having for both, and the only
part that differs is how the booking is cancelled: a member cancels from their
own account, so their mail carries no code, and somebody without an account has
no account to be checked against, so theirs carries one.

The page says the same thing when the booking is made. This mail complements the
on-page confirmation, and the message on the page stays whether or not the
booker gave an address.
"""

from urllib.parse import urlsplit

from django.conf import settings
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from core.utils import enqueue_task_on_commit, send_email_with_attachments_task

from . import access
from .ics import invite_attachment


def notify_booker(booking, *, request):
    """Tell the booker that the booking is registered, and how to cancel it."""
    recipient = _recipient(booking)
    if not recipient:
        return
    # Decided in one place, from the same fact the code is: a member cancels from
    # the page that checks their account, and somebody without one has only the
    # code, so their link goes to the page that takes it. Splitting this between
    # the caller and here is how a member ends up being sent to a page asking for
    # a code they were never given.
    if booking.is_external:
        cancel_url = _site_base(request) + reverse('booking:cancel')
        cancel_code = access.cancel_code(booking)
    else:
        cancel_url = _site_base(request) + reverse('booking:my_bookings')
        cancel_code = None
    context = {
        'booking': booking,
        'room': booking.room,
        'start_local': timezone.localtime(booking.start),
        'end_local': timezone.localtime(booking.end),
        'cancel_url': cancel_url,
        'cancel_code': cancel_code,
        # An email body is rendered without a request, so the context processor
        # that exposes the association's address to templates does not run here.
        'association_email': getattr(settings, 'CONTENT_VARIABLES', {}).get('ASSOCIATION_EMAIL', ''),
        # The footer links to the site itself, which is a different thing from
        # the page that cancels this booking.
        'site_url': _site_base(request) + '/',
    }
    subject = _('Bokningsbekräftelse för %(room)s') % {'room': booking.room.name}
    body = render_to_string('booking/email/booking_confirmation.txt', context)
    html = render_to_string('booking/email/booking_confirmation.html', context)
    enqueue_task_on_commit(
        send_email_with_attachments_task,
        subject,
        body,
        settings.DEFAULT_FROM_EMAIL,
        [recipient],
        html_message=html,
        attachments=(
            invite_attachment(
                booking=booking,
                room=booking.room,
                start=booking.start,
                end=booking.end,
                cancel_url=cancel_url,
                host=_invite_namespace(request),
            ),
        ),
    )


def _site_base(request):
    """The association's public address, without a trailing slash.

    Not the host this request arrived on: behind the ingress the request carries
    an internal name, and a mail that tells a booker to visit it is worse than no
    link at all. The content variable is what the rest of the project's mail
    uses, and the request is only the fallback so a development instance still
    links to itself.
    """
    base = str(getattr(settings, 'CONTENT_VARIABLES', {}).get('SITE_URL', '') or '')
    if base:
        return base.rstrip('/')
    return request.build_absolute_uri('/').rstrip('/')


def _invite_namespace(request):
    """What keeps this installation's calendar events apart from another's.

    The public address when there is one, so the identity of an event does not
    move when a request arrives through a different host, and the request's host
    only as the fallback.
    """
    return urlsplit(_site_base(request)).netloc or request.get_host()


def _recipient(booking):
    """Where to send it, which is the account for a member and the typed
    address otherwise."""
    if booking.author_id:
        return booking.author.email
    return booking.booker_email
