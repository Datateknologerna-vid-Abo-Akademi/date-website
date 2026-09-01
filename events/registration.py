from dataclasses import dataclass

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils.timezone import now
from django.utils.translation import gettext_lazy as _

from events.models import EventAttendees, EventRegistrationForm


class EventSignupError(Exception):
    def __init__(self, message, field=None):
        self.message = message
        self.field = field
        super().__init__(message)


class _AttendeeNrCollision(Exception):
    # Raised when attendee_nr allocation hits the unique constraint; the
    # whole signup is retried by register_event_signup.
    pass


# How many times a rolled-back signup is retried after an attendee_nr
# allocation collision, on top of the initial attempt, before giving up.
_MAX_ATTENDEE_NR_RETRIES = 5

_ATTENDEE_NR_CONSTRAINT_NAME = 'unique_attendee_nr_per_event'


@dataclass
class EventSignupResult:
    attendee: EventAttendees
    avec_attendee: EventAttendees | None = None

    @property
    def attendees(self):
        return [attendee for attendee in (self.attendee, self.avec_attendee) if attendee is not None]


def get_registration_questions(event):
    return list(EventRegistrationForm.objects.filter(event=event).order_by('choice_number'))


def get_public_registration_questions(event):
    return list(EventRegistrationForm.objects.filter(event=event, public_info=True).order_by('choice_number'))


def registration_preferences(questions, cleaned_data, *, prefix=""):
    preferences = {}
    for question in questions:
        key = f"{prefix}{question.name}"
        preferences[str(question)] = cleaned_data.get(key)
    return preferences


def register_event_signup(event, cleaned_data):
    required_places = 2 if cleaned_data.get('avec') else 1
    if cleaned_data.get('avec'):
        _validate_avec(cleaned_data)

    questions = get_registration_questions(event)

    # attendee_nr is allocated as max+10 from an unlocked read for unlimited
    # events (they skip the row lock), so concurrent signups can pick the same
    # next number. The unique constraint on (event, attendee_nr) turns that
    # race into a retryable conflict; retry the whole (rolled back) attempt,
    # bounded, since each retry re-reads the current maximum.
    for _attempt in range(_MAX_ATTENDEE_NR_RETRIES + 1):
        try:
            return _register_event_signup_once(event, cleaned_data, required_places, questions)
        except _AttendeeNrCollision:
            continue
    raise EventSignupError(_("Det gick inte att anmäla dig just nu, försök igen."))


def _register_event_signup_once(event, cleaned_data, required_places, questions):
    with transaction.atomic():
        # The caller's Event object may be stale (it was loaded before the
        # request), so refresh the row first and decide the locking strategy
        # from the current database state. Only capacity-limited child events
        # need the row lock: their capacity check must be atomic against
        # concurrent signups. Unlimited parent/standalone events keep
        # accepting an overflow list, so skip the lock and let concurrent
        # signups to the same event proceed in parallel (duplicate emails
        # are still caught by the unique constraint on (event, email)).
        qs = event.__class__.objects.select_related('parent')
        event = qs.get(pk=event.pk)
        if event.parent is not None and event.sign_up_max_participants != 0:
            event = qs.select_for_update(of=('self',)).get(pk=event.pk)
        _ensure_capacity(event, required_places)
        attendee = _create_attendee(
            event=event,
            user=cleaned_data['user'],
            email=cleaned_data['email'],
            anonymous=cleaned_data['anonymous'],
            preferences=registration_preferences(questions, cleaned_data),
        )
        avec_attendee = None
        if cleaned_data.get('avec'):
            avec_attendee = _create_attendee(
                event=event,
                user=cleaned_data['avec_user'],
                email=cleaned_data['avec_email'],
                anonymous=cleaned_data['avec_anonymous'],
                preferences=registration_preferences(questions, cleaned_data, prefix="avec_"),
                avec_for=attendee,
                duplicate_field='avec_email',
            )

    # Residual race: an event changed from unlimited to capacity-limited
    # between the fresh read and the insert can slip past _ensure_capacity
    # without the lock. This requires an admin edit in that window, is not
    # serialized, and is accepted as a consistency boundary: capacity changes
    # take effect from the next signup on. Avoid changing the capacity mode
    # while registrations are active if strict atomicity is required.

    return EventSignupResult(attendee=attendee, avec_attendee=avec_attendee)


def _ensure_capacity(event, required_places):
    # Only child events enforce a hard capacity limit. A full parent/standalone
    # event keeps accepting signups as an overflow/reserve list (see
    # templates/common/events/registering.html for the matching UI message).
    if not event.parent:
        return
    if event.sign_up_max_participants == 0:
        return
    if event.remaining_places() < required_places:
        raise EventSignupError(_("Evenemanget är fullt."))


def _validate_avec(cleaned_data):
    if not cleaned_data.get('avec_user'):
        raise EventSignupError(_("Ange namn för avec."), field='avec_user')
    if not cleaned_data.get('avec_email'):
        raise EventSignupError(_("Ange e-post för avec."), field='avec_email')


def _create_attendee(event, user, email, anonymous, preferences, avec_for=None, duplicate_field='email'):
    storage_event = event.parent or event
    try:
        return EventAttendees.objects.create(
            user=user,
            event=storage_event,
            email=email,
            time_registered=now(),
            preferences=preferences,
            anonymous=anonymous,
            avec_for=avec_for,
            original_event=event,
        )
    except IntegrityError as exc:
        if _is_attendee_nr_collision(exc):
            raise _AttendeeNrCollision from exc
        raise EventSignupError(
            _("Det finns redan någon anmäld med denna email"),
            field=duplicate_field,
        ) from exc
    except ValidationError as exc:
        raise EventSignupError(exc.messages[0] if exc.messages else str(exc), field=duplicate_field) from exc


def _is_attendee_nr_collision(exc):
    # Distinguish a (event, attendee_nr) allocation conflict (retryable race
    # on the unlocked max+10 allocation) from a duplicate (event, email)
    # (a real user error). Django wraps the driver error in IntegrityError;
    # psycopg exposes the constraint name via diag, SQLite only the message.
    cause = exc.__cause__
    if cause is None:
        return False
    constraint = getattr(getattr(cause, 'diag', None), 'constraint_name', None)
    if constraint:
        return constraint == _ATTENDEE_NR_CONSTRAINT_NAME
    return 'attendee_nr' in str(cause)
