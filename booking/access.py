"""Access gate for the public room-booking pages.

The booking code is never stored anywhere. It is derived from the server secret
and a generation counter that only moves when the board rotates the code, so
there is no schedule to run and the current code can be displayed read-only in
the admin. Unlocking a visitor is only a session token for the current
generation, which means a rotation invalidates every existing unlock by itself
and the typed code is never written to the session.
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


def _secret_bytes():
    """The server secret as bytes, whatever form the settings hold it in."""
    secret = settings.SECRET_KEY
    return secret.encode() if isinstance(secret, str) else secret


def _generation(access_settings=None):
    if access_settings is None:
        access_settings = BookingSettings.get_solo()
    return access_settings.code_generation


def code_for_generation(generation):
    """Derive the fixed-width numeric code for a generation from SECRET_KEY."""
    digest = hmac.new(
        _secret_bytes(),
        f'booking-code:{generation}'.encode(),
        hashlib.sha256,
    ).digest()
    number = int.from_bytes(digest[:8], 'big') % (10**BOOKING_CODE_DIGITS)
    return str(number).zfill(BOOKING_CODE_DIGITS)


def current_code(access_settings=None):
    """The code that is valid now.

    Nothing about it depends on the clock. It changes when the board rotates it
    and at no other moment, so no schedule has to run for it to stay correct.
    """
    return code_for_generation(_generation(access_settings))


def accepted_codes(at=None, access_settings=None):
    """The current code, plus the previous one while its grace period lasts.

    The grace period is anchored to the moment the board rotated the code, not
    to a calendar boundary and not to the current request, so it does not slide
    forward with every visit. A booker who was handed the old code a minute
    before the rotation is not stranded by it.
    """
    if access_settings is None:
        access_settings = BookingSettings.get_solo()
    codes = [code_for_generation(access_settings.code_generation)]
    rotated_at = access_settings.rotated_at
    if rotated_at is not None and access_settings.code_generation > 1:
        elapsed = _as_local(at) - _as_local(rotated_at)
        if datetime.timedelta(0) <= elapsed < BOOKING_CODE_GRACE:
            codes.append(code_for_generation(access_settings.code_generation - 1))
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


def session_token(access_settings=None) -> str:
    """Opaque token for the current generation, recording an unlock.

    It is HMAC'd rather than a bare hash of the six-digit code, and it depends
    on the generation, so rotating the code ends every existing unlock with no
    stored expiry anywhere. The digest is returned hex-encoded because the
    default session serializer is JSON and cannot store bytes.
    """
    return hmac.new(
        _secret_bytes(),
        f'booking-session:{_generation(access_settings)}'.encode(),
        hashlib.sha256,
    ).hexdigest()


def _stored_token(value) -> str:
    """Normalise whatever the session holds into the hex token form."""
    return value.hex() if isinstance(value, bytes) else value


def session_has_access(request, access_settings=None) -> bool:
    stored = request.session.get(BOOKING_SESSION_TOKEN_KEY)
    if not stored:
        return False
    stored = _stored_token(stored)
    return hmac.compare_digest(stored, session_token(access_settings=access_settings))


def grant_session(request, access_settings=None):
    request.session[BOOKING_SESSION_TOKEN_KEY] = session_token(access_settings=access_settings)
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
    including the request that hits the attempt limit. A POST must also pass the
    captcha before the code is looked at.
    """
    from .forms import BookingCodeForm

    context = dict(context or {})
    lockout = lockout_remaining(request)
    form = BookingCodeForm(at=at, access_settings=access_settings)
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
            form = BookingCodeForm(request.POST, at=at, access_settings=access_settings)
            if form.is_valid():
                grant_session(request, access_settings=access_settings)
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
