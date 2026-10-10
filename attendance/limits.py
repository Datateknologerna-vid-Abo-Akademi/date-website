"""Wrong-code attempts and the lockout that follows them.

The counter lives in the session, the same choice the booking gate makes and for
the same reason: there is nothing else to key it on that a client cannot
discard. What that bounds, and what it does not, is recorded in the developer
notes.

The lockout is short on purpose. The code is displayed in the room, so the
likely user of this path is a participant who mistyped it, and stranding them
for a quarter of an hour would cost more than the guessing it prevents.
"""

from math import ceil

from django.http import HttpRequest
from django.utils.timezone import now

ATTEMPT_LIMIT = 5
LOCKOUT_SECONDS = 60

ATTEMPTS_SESSION_KEY = "attendance_code_attempts"
LOCKOUT_SESSION_KEY = "attendance_code_lockout_until"


def lockout_remaining(request: HttpRequest) -> int:
    """Seconds left in the lockout, or 0. An expired lockout is cleared."""
    until = request.session.get(LOCKOUT_SESSION_KEY)
    if until is None:
        return 0

    remaining = until - now().timestamp()
    if remaining <= 0:
        clear(request)
        return 0

    return ceil(remaining)


def register_failure(request: HttpRequest) -> None:
    """Count one wrong code, and start the lockout once the limit is reached."""
    used = request.session.get(ATTEMPTS_SESSION_KEY, 0) + 1
    request.session[ATTEMPTS_SESSION_KEY] = used
    if used >= ATTEMPT_LIMIT:
        request.session[LOCKOUT_SESSION_KEY] = now().timestamp() + LOCKOUT_SECONDS


def clear(request: HttpRequest) -> None:
    """Forget the attempts and any lockout, after a code was accepted."""
    request.session.pop(ATTEMPTS_SESSION_KEY, None)
    request.session.pop(LOCKOUT_SESSION_KEY, None)
