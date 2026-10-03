"""Calendar invites for confirmed bookings.

The invite rides along with the confirmation mail so the time lands in the
booker's own calendar without being typed in again. It is published rather than
sent as a request (``METHOD:PUBLISH``): the mail comes from an automated
address, and an invite that reads as coming from a person makes clients offer a
reply that nobody reads. For the same reason there is no ``ATTENDEE``, no
``ORGANIZER`` and no ``VALARM`` in the event.
"""

import datetime
from typing import Any

from django.utils import timezone
from django.utils.translation import gettext as _

from .models import Booking, Room

# RFC 5545 limits a content line to 75 octets, and the single leading space of a
# continuation line counts towards its own budget.
_LINE_OCTETS = 75
_CRLF = '\r\n'

# The UID has to come out the same every time the invite is generated, so that a
# re-sent confirmation updates the event the booker already has instead of adding
# a second one. It is derived from the booking's key alone: not from the times,
# which the board may correct, and not from the site address, which the
# association may change. The domain part only has to be unique, and ``.invalid``
# is reserved, so no real calendar can collide with this one.
_UID_DOMAIN = 'booking.invalid'

PRODID = '-//date-website//Booking//SV'

ATTACHMENT_MIMETYPE = 'text/calendar; method=PUBLISH; charset=utf-8'


def booking_invite(
    *,
    booking: Booking,
    room: Room,
    start: datetime.datetime,
    end: datetime.datetime,
    cancel_url: str = '',
    host: str = '',
) -> str:
    """The complete iCalendar file for one published booking event.

    A plain function rather than a model method, because the mail is rendered
    outside any request and needs nothing from a database connection beyond the
    two rows it is handed.
    """
    lines = [
        'BEGIN:VCALENDAR',
        'VERSION:2.0',
        f'PRODID:{PRODID}',
        'METHOD:PUBLISH',
        'BEGIN:VEVENT',
        f'UID:{_uid(booking, host)}',
        f'DTSTAMP:{_utc_stamp(timezone.now())}',
        f'DTSTART:{_utc_stamp(start)}',
        f'DTEND:{_utc_stamp(end)}',
        f'SUMMARY:{_escape_text(room.name)}',
        f'DESCRIPTION:{_escape_text(_description(booking, cancel_url))}',
        'STATUS:CONFIRMED',
    ]
    if cancel_url:
        lines.append(f'URL:{cancel_url}')
    lines += ['END:VEVENT', 'END:VCALENDAR']
    return ''.join(f'{_fold(line)}{_CRLF}' for line in lines)


def invite_attachment(**kwargs: Any) -> tuple[str, str, str]:
    """The invite as the ``(filename, content, mimetype)`` an attachment needs."""
    content = booking_invite(**kwargs)
    return f'booking-{kwargs["booking"].pk}.ics', content, ATTACHMENT_MIMETYPE


def _uid(booking: Booking, host: str = '') -> str:
    """A stable identity for the event, unique beyond this installation.

    The primary key alone would collide with another association's booking of the
    same number, and a calendar that sees both would treat them as one event and
    replace the first with the second. The host supplies the namespace, and the
    reserved domain is the fallback for a caller that has no request.
    """
    return f'booking-{booking.pk}@{host or _UID_DOMAIN}'


def _utc_stamp(moment: datetime.datetime) -> str:
    """A DTSTART/DTEND/DTSTAMP value: UTC, in the form clients expect."""
    return moment.astimezone(datetime.UTC).strftime('%Y%m%dT%H%M%SZ')


def _description(booking: Booking, cancel_url: str) -> str:
    """What the booker wrote, and where to get rid of the booking.

    An event opened in a calendar shows this text and nothing else from the
    mail, so the cancellation hint belongs here as well as in the body.
    """
    parts = [(booking.description or '').strip()]
    if cancel_url:
        parts.append(_('Bokningen kan avbokas på %(url)s.') % {'url': cancel_url})
    return '\n'.join(part for part in parts if part)


def _escape_text(value: str) -> str:
    """Escape a TEXT value as RFC 5545 requires.

    The backslash goes first: escaping it after the others would double the
    backslashes the others introduce and turn an escaped comma into a literal
    one.
    """
    return (
        value.replace('\\', '\\\\')
        .replace('\r\n', '\\n')
        .replace('\n', '\\n')
        .replace('\r', '\\n')
        .replace(';', '\\;')
        .replace(',', '\\,')
    )


def _fold(line: str) -> str:
    """Break one content line into pieces of at most 75 octets.

    The limit counts bytes, and a Swedish description is mostly two-byte
    letters, so folding on character count would hand a client lines it may
    refuse. A character is never split: it moves whole to the next piece.
    """
    pieces = []
    current: list[str] = []
    used = 0
    limit = _LINE_OCTETS
    for char in line:
        width = len(char.encode('utf-8'))
        if used + width > limit:
            pieces.append(''.join(current))
            current = []
            used = 0
            # The space that marks a continuation line is part of its budget.
            limit = _LINE_OCTETS - 1
        current.append(char)
        used += width
    pieces.append(''.join(current))
    return f'{_CRLF} '.join(pieces)
