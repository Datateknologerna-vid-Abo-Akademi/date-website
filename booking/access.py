"""Access gate for the public room-booking pages.

Every room has its own booking code, and none of them is stored anywhere. A code
is derived from the server secret, the room and a per-room generation counter
that only moves when the board rotates that room's code, so there is no schedule
to run, one room's code can be handed out without handing out another's, and a
leak is contained to the room it leaked from. Unlocking a visitor is a session
token stored per room for that room's current generation, so rotating a room
invalidates exactly the unlocks it granted and the typed code is never written
to the session.
"""

import datetime
import hashlib
import hmac
import math
import time

from django.conf import settings
from django.shortcuts import redirect, render
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from core.utils import validate_captcha

# All three hold a mapping keyed by room primary key as text, because the
# default session serializer is JSON and JSON object keys are strings.
BOOKING_SESSION_TOKEN_KEY = 'booking_access_token'  # noqa: S105 (session key, not a password)
BOOKING_ATTEMPTS_COUNTER = 'booking_code_attempts'
BOOKING_LOCKOUT_UNTIL = 'booking_code_lockout_until'
BOOKING_ATTEMPT_LIMIT = 5
BOOKING_LOCKOUT_SECONDS = 15 * 60
BOOKING_CODE_GRACE = datetime.timedelta(minutes=15)
BOOKING_CODE_DIGITS = 6


def now_at():
    """The one time seam: tests patch this to pin "now"."""
    return timezone.now()


def _as_local(at):
    """Return ``at`` as an aware datetime in the association's timezone.

    Naive input is treated as already local, so callers can pass plain
    datetimes without thinking about UTC.
    """
    if at is None:
        at = now_at()
    if not timezone.is_aware(at):
        return timezone.make_aware(at, timezone.get_current_timezone())
    return timezone.localtime(at)


def _elapsed_since(start, at=None):
    """Time actually passed between ``start`` and ``at``.

    Both sides go through UTC first. Subtracting two aware datetimes that share
    a ``tzinfo`` compares their naive parts, so a pair straddling a daylight
    saving change would measure wall-clock time instead of elapsed time: in
    Helsinki, 03:55+03:00 to 04:00+02:00 is five minutes by wall clock and an
    hour and five in reality, which is long enough to keep a rotated code alive
    for an extra hour or to end its grace period an hour early.
    """
    return _as_local(at).astimezone(datetime.UTC) - _as_local(start).astimezone(datetime.UTC)


def _secret_bytes():
    """The server secret as bytes, whatever form the settings hold it in."""
    secret = settings.SECRET_KEY
    return secret.encode() if isinstance(secret, str) else secret


def code_for_generation(room, generation):
    """Derive a room's fixed-width numeric code for one of its generations.

    The room goes into the message, so two rooms on the same generation do not
    share a code and one room's code says nothing about another's.
    """
    digest = hmac.new(
        _secret_bytes(),
        f'booking-code:{room.pk}:{generation}'.encode(),
        hashlib.sha256,
    ).digest()
    number = int.from_bytes(digest[:8], 'big') % (10**BOOKING_CODE_DIGITS)
    return str(number).zfill(BOOKING_CODE_DIGITS)


def current_code(room):
    """The room's code that is valid now.

    Nothing about it depends on the clock. It changes when the board rotates
    that room and at no other moment, so no schedule has to run for it to stay
    correct, and rotating one room leaves the others alone.
    """
    return code_for_generation(room, room.code_generation)


def accepted_codes(room, at=None):
    """The current code, plus the previous one while its grace period lasts.

    The grace period is anchored to the moment the board rotated the code, not
    to a calendar boundary and not to the current request, so it does not slide
    forward with every visit. A booker who was handed the old code a minute
    before the rotation is not stranded by it.
    """
    codes = [code_for_generation(room, room.code_generation)]
    rotated_at = room.rotated_at
    if rotated_at is not None and room.code_generation > 1:
        elapsed = _elapsed_since(rotated_at, at)
        if datetime.timedelta(0) <= elapsed < BOOKING_CODE_GRACE:
            codes.append(code_for_generation(room, room.code_generation - 1))
    return tuple(codes)


def check_code(room, candidate, at=None):
    """Constant-time check of a typed code, with no early exit.

    The comparison is on encoded bytes: ``hmac.compare_digest`` raises
    TypeError for non-ASCII text, and the code field accepts anything a
    visitor types, so comparing text directly would turn a stray letter such
    as "å" into a server error instead of a rejected code.
    """
    candidate = (candidate or '').strip()
    if not candidate:
        return False
    candidate_bytes = candidate.encode()
    matched = False
    for accepted in accepted_codes(room, at=at):
        matched = hmac.compare_digest(candidate_bytes, accepted.encode()) or matched
    return matched


def cancel_code(booking) -> str:
    """The code that lets one booking be cancelled, derived and never stored.

    It is derived from the booking's primary key and the server secret, the same
    way the room codes are, so nothing new has to be stored and the code cannot
    be recomputed by anyone who only knows the booking number. It is longer than
    a room code on purpose: a room code is typed by people who were told it, and
    this one is copied out of an email and then used to delete a row, so it has
    to be beyond guessing rather than merely inconvenient.
    """
    return hmac.new(
        _secret_bytes(),
        f'booking-cancel:{booking.pk}'.encode(),
        hashlib.sha256,
    ).hexdigest()[:12]


def booking_with_cancel_code(code, at=None):
    """The upcoming booking a cancellation code belongs to, or ``None``.

    Finding it means deriving the code for each upcoming booking and comparing,
    because the code is not stored anywhere to look up. Only upcoming bookings
    are considered, which is also exactly the set that may be cancelled.
    """
    candidate = (code or '').strip().lower()
    if not candidate:
        return None
    from .models import Booking

    upcoming = Booking.objects.filter(end__gte=_as_local(at)).select_related('room')
    for booking in upcoming:
        if hmac.compare_digest(cancel_code(booking), candidate):
            return booking
    return None


def session_token(room) -> str:
    """Opaque token for a room's current generation, recording an unlock.

    It is HMAC'd rather than a bare hash of the six-digit code, and it depends
    on the room and its generation, so rotating a room ends exactly the unlocks
    that room granted, with no stored expiry anywhere. The digest is returned
    hex-encoded because the default session serializer is JSON and cannot store
    bytes.
    """
    return hmac.new(
        _secret_bytes(),
        f'booking-session:{room.pk}:{room.code_generation}'.encode(),
        hashlib.sha256,
    ).hexdigest()


def _stored_token(value) -> str:
    """Normalise whatever the session holds into the hex token form."""
    return value.hex() if isinstance(value, bytes) else value


def _room_state(request, key):
    """The per-room mapping a session key holds, ignoring anything else.

    A session written by an older release holds a bare token or counter under
    these keys rather than a mapping. It is treated as empty instead of being
    migrated: the visitor is asked for the code once more and the session heals.
    """
    stored = request.session.get(key)
    return stored if isinstance(stored, dict) else {}


def _room_key(room):
    return str(room.pk)


def session_has_access(request, room) -> bool:
    stored = _room_state(request, BOOKING_SESSION_TOKEN_KEY).get(_room_key(room))
    if not stored:
        return False
    stored = _stored_token(stored)
    return hmac.compare_digest(stored, session_token(room))


def grant_session(request, room):
    """Record the unlock for this room, and clear this room's code attempts."""
    tokens = dict(_room_state(request, BOOKING_SESSION_TOKEN_KEY))
    tokens[_room_key(room)] = session_token(room)
    request.session[BOOKING_SESSION_TOKEN_KEY] = tokens
    _clear_room_state(request, BOOKING_ATTEMPTS_COUNTER, room)
    _clear_room_state(request, BOOKING_LOCKOUT_UNTIL, room)


def _clear_room_state(request, key, room):
    """Forget this room's entry, and the key itself once nothing is left."""
    state = dict(_room_state(request, key))
    if _room_key(room) in state:
        del state[_room_key(room)]
        if state:
            request.session[key] = state
        else:
            request.session.pop(key, None)


def attempts_used(request, room):
    """How many wrong codes this visitor has typed for this room."""
    return int(_room_state(request, BOOKING_ATTEMPTS_COUNTER).get(_room_key(room), 0))


def record_failed_attempt(request, room):
    """Count a wrong code for this room and lock the room out at the limit."""
    attempts = attempts_used(request, room) + 1
    counters = dict(_room_state(request, BOOKING_ATTEMPTS_COUNTER))
    counters[_room_key(room)] = attempts
    request.session[BOOKING_ATTEMPTS_COUNTER] = counters
    if attempts >= BOOKING_ATTEMPT_LIMIT:
        until = dict(_room_state(request, BOOKING_LOCKOUT_UNTIL))
        until[_room_key(room)] = time.time() + BOOKING_LOCKOUT_SECONDS
        request.session[BOOKING_LOCKOUT_UNTIL] = until
    return attempts


def lockout_remaining(request, room):
    """Seconds left in this room's lockout, clearing it once it has passed."""
    until = _room_state(request, BOOKING_LOCKOUT_UNTIL).get(_room_key(room))
    if not until:
        return 0
    remaining = int(until - time.time())
    if remaining <= 0:
        _clear_room_state(request, BOOKING_LOCKOUT_UNTIL, room)
        _clear_room_state(request, BOOKING_ATTEMPTS_COUNTER, room)
        return 0
    return remaining


def captcha_response(request):
    """The Turnstile response, normalised so a missing field fails locally.

    ``core.utils.validate_captcha`` only short-circuits on an empty string, so
    handing it None would send a verification request to Cloudflare, with its
    five second timeout, for every request that simply omits the field.
    """
    return request.POST.get('cf-turnstile-response') or ''


def is_code_submission(request):
    """Whether a POST carries the code form rather than the booking form.

    The room page serves both forms and the booking form has no ``code`` field,
    so a submitted code is handled by the gate even when the visitor has already
    unlocked the room, for example from an older tab.
    """
    return 'code' in request.POST


def booking_code_gate(
    request,
    *,
    room,
    template_name,
    context=None,
    next_url,
    at=None,
):
    """Render the code gate, or redirect to ``next_url`` after a valid code.

    ``next_url`` is a URL name or an already resolved URL chosen by the view,
    never a target taken from the request. Behaviour mirrors the exam bank
    gate: a fresh gate is 200, a wrong code is 403, and a lockout is 429,
    including the request that hits the attempt limit. A POST must also pass the
    captcha before the code is looked at.

    The room instance is the one snapshot the whole request works from, so the
    code that is checked and the token that is stored belong to the same
    generation: re-reading the room when the unlock is granted would open a
    window where a rotation lands between the two and hands the visitor an
    unlock for a generation whose code they never knew.
    """
    from .forms import BookingCodeForm

    context = dict(context or {})
    lockout = lockout_remaining(request, room)
    form = BookingCodeForm(room=room, at=at)
    status = 200

    if lockout:
        status = 429
    elif request.method == 'POST':
        if not validate_captcha(captcha_response(request)):
            # Deliberately does not build a bound form. Validating the submitted
            # code here would tell a client that has not passed the challenge
            # whether its guess was right, one guess at a time, without
            # consuming an attempt. A rejected challenge is not a code attempt,
            # so it must not count against the visitor's five either.
            context['captcha_error'] = _('Kunde inte verifiera att du inte är en robot. Försök igen.')
            status = 403
        else:
            form = BookingCodeForm(request.POST, room=room, at=at)
            if form.is_valid():
                grant_session(request, room)
                return redirect(next_url)
            if record_failed_attempt(request, room) >= BOOKING_ATTEMPT_LIMIT:
                lockout = BOOKING_LOCKOUT_SECONDS
                status = 429
            else:
                status = 403

    context['code_form'] = form
    context['lockout_remaining'] = lockout
    # The template speaks in minutes; the raw value is seconds.
    context['lockout_minutes'] = math.ceil(lockout / 60) if lockout else 0
    return render(request, template_name, context, status=status)
