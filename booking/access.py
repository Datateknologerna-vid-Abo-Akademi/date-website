"""Access gate for the public room-booking pages.

The booking code is never stored anywhere. It is derived from the server secret
and the current time slot, so rotating the code needs no scheduled task and the
current code can be displayed read-only in the admin. Unlocking a visitor is
only a session token for the current slot, which means a rotation invalidates
every existing unlock by itself and the typed code is never written to the
session.
"""

import calendar
import datetime
import hashlib
import hmac
import math
import time

from django.conf import settings
from django.shortcuts import redirect, render
from django.utils import timezone

from .models import BookingSettings

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


def _slot_start(rotation_period, at):
    """Start of the slot that contains ``at``, in local time."""
    local = _as_local(at)
    if rotation_period == BookingSettings.ROTATION_MONTHLY:
        return local.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if rotation_period == BookingSettings.ROTATION_DAILY:
        return local.replace(hour=0, minute=0, second=0, microsecond=0)
    midnight = local.replace(hour=0, minute=0, second=0, microsecond=0)
    return midnight - datetime.timedelta(days=midnight.weekday())


def slot_for(rotation_period, at=None):
    """Return ``(slot_key, slot_start)`` for the slot containing ``at``.

    The key is prefixed with the rotation period so that changing the period
    always changes the slot, even when the calendar part happens to repeat.
    """
    start = _slot_start(rotation_period, at)
    if rotation_period == BookingSettings.ROTATION_MONTHLY:
        calendar_part = start.strftime('%Y-%m')
    else:
        calendar_part = start.strftime('%Y-%m-%d')
    return f'{rotation_period}:{calendar_part}', start


def _secret_bytes():
    """The server secret as bytes, whatever form the settings hold it in."""
    secret = settings.SECRET_KEY
    return secret.encode() if isinstance(secret, str) else secret


def code_for_slot(slot):
    """Derive the fixed-width numeric code for a slot from SECRET_KEY."""
    digest = hmac.new(
        _secret_bytes(),
        f'booking-code:{slot}'.encode(),
        hashlib.sha256,
    ).digest()
    number = int.from_bytes(digest[:8], 'big') % (10**BOOKING_CODE_DIGITS)
    return str(number).zfill(BOOKING_CODE_DIGITS)


def _rotation_period(access_settings=None):
    if access_settings is None:
        access_settings = BookingSettings.get_solo()
    return access_settings.rotation_period


def _slot_offset(rotation_period, at, offset):
    """Start of the slot ``offset`` slots before the slot containing ``at``."""
    start = _slot_start(rotation_period, at)
    if rotation_period == BookingSettings.ROTATION_MONTHLY:
        month = start.month - offset
        year = start.year
        while month < 1:
            month += 12
            year -= 1
        return start.replace(year=year, month=month)
    days = 1 if rotation_period == BookingSettings.ROTATION_DAILY else 7
    return start - datetime.timedelta(days=days * offset)


def current_code(at=None, access_settings=None):
    """The code that is valid right now."""
    rotation_period = _rotation_period(access_settings)
    slot, _start = slot_for(rotation_period, at)
    return code_for_slot(slot)


def next_rotation(at=None, access_settings=None):
    """Start of the slot that follows the one containing ``at``."""
    rotation_period = _rotation_period(access_settings)
    start = _slot_start(rotation_period, at)
    if rotation_period == BookingSettings.ROTATION_MONTHLY:
        last_day = calendar.monthrange(start.year, start.month)[1]
        return start.replace(day=last_day) + datetime.timedelta(days=1)
    if rotation_period == BookingSettings.ROTATION_DAILY:
        return start + datetime.timedelta(days=1)
    return start + datetime.timedelta(days=7)


def accepted_codes(at=None, access_settings=None):
    """The current code, plus the previous one while the grace period lasts.

    The grace period keeps a code that was just displayed in the admin working
    for a while, and it is anchored to the start of the slot so it does not
    slide forward with every request.
    """
    rotation_period = _rotation_period(access_settings)
    _slot, start = slot_for(rotation_period, at)
    codes = [code_for_slot(_slot)]
    if _as_local(at) - start < BOOKING_CODE_GRACE:
        previous_start = _slot_offset(rotation_period, start, 1)
        previous_slot, _previous_start = slot_for(rotation_period, previous_start)
        codes.append(code_for_slot(previous_slot))
    return tuple(codes)


def check_code(candidate, at=None, access_settings=None):
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
    for accepted in accepted_codes(at=at, access_settings=access_settings):
        matched = hmac.compare_digest(candidate_bytes, accepted.encode()) or matched
    return matched


def session_token(at=None, access_settings=None) -> str:
    """Opaque per-slot token that records an unlock in the session.

    It is HMAC'd rather than a bare hash of the six-digit code, and it depends
    on the slot, so a rotation ends the unlock without any stored expiry. The
    digest is returned hex-encoded because the default session serializer is
    JSON and cannot store bytes.
    """
    rotation_period = _rotation_period(access_settings)
    slot, _start = slot_for(rotation_period, at)
    return (
        hmac.new(
            _secret_bytes(),
            f'booking-session:{slot}'.encode(),
            hashlib.sha256,
        )
        .digest()[:32]
        .hex()
    )


def _stored_token(value) -> str:
    """Normalise whatever the session holds into the hex token form."""
    return value.hex() if isinstance(value, bytes) else value


def session_has_access(request, at=None, access_settings=None) -> bool:
    stored = request.session.get(BOOKING_SESSION_TOKEN_KEY)
    if not stored:
        return False
    stored = _stored_token(stored)
    return hmac.compare_digest(stored, session_token(at=at, access_settings=access_settings))


def grant_session(request, at=None, access_settings=None):
    request.session[BOOKING_SESSION_TOKEN_KEY] = session_token(at=at, access_settings=access_settings)
    request.session.pop(BOOKING_ATTEMPTS_COUNTER, None)
    request.session.pop(BOOKING_LOCKOUT_UNTIL, None)


def lockout_remaining(request):
    """Seconds left in the current lockout, clearing it once it has passed."""
    until = request.session.get(BOOKING_LOCKOUT_UNTIL)
    if not until:
        return 0
    remaining = int(until - time.time())
    if remaining <= 0:
        request.session.pop(BOOKING_LOCKOUT_UNTIL, None)
        request.session.pop(BOOKING_ATTEMPTS_COUNTER, None)
        return 0
    return remaining


def booking_code_gate(
    request,
    *,
    template_name,
    context=None,
    next_url,
    at=None,
    access_settings=None,
):
    """Render the code gate, or redirect to ``next_url`` after a valid code.

    ``next_url`` is a URL name or an already resolved URL chosen by the view,
    never a target taken from the request. Behaviour mirrors the exam bank
    gate: a fresh gate is 200, a wrong code is 403, and a lockout is 429,
    including the request that hits the attempt limit.
    """
    from .forms import BookingCodeForm

    context = dict(context or {})
    lockout = lockout_remaining(request)
    form = BookingCodeForm(at=at, access_settings=access_settings)
    status = 200

    if lockout:
        status = 429
    elif request.method == 'POST':
        form = BookingCodeForm(request.POST, at=at, access_settings=access_settings)
        if form.is_valid():
            grant_session(request, at=at, access_settings=access_settings)
            return redirect(next_url)
        attempts = request.session.get(BOOKING_ATTEMPTS_COUNTER, 0) + 1
        request.session[BOOKING_ATTEMPTS_COUNTER] = attempts
        if attempts >= BOOKING_ATTEMPT_LIMIT:
            request.session[BOOKING_LOCKOUT_UNTIL] = time.time() + BOOKING_LOCKOUT_SECONDS
            lockout = BOOKING_LOCKOUT_SECONDS
            status = 429
        else:
            status = 403

    context['code_form'] = form
    context['lockout_remaining'] = lockout
    # The template speaks in minutes; the raw value is seconds.
    context['lockout_minutes'] = math.ceil(lockout / 60) if lockout else 0
    return render(request, template_name, context, status=status)
