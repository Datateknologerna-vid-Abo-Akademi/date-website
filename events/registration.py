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


def registration_preferences(event, cleaned_data, *, prefix=""):
    preferences = {}
    for question in get_registration_questions(event):
        key = f"{prefix}{question.name}"
        preferences[str(question)] = cleaned_data.get(key)
    return preferences


def register_event_signup(event, cleaned_data):
    required_places = 2 if cleaned_data.get('avec') else 1
    if cleaned_data.get('avec'):
        _validate_avec(cleaned_data)

    with transaction.atomic():
        event = event.__class__.objects.select_for_update().select_related('parent').get(pk=event.pk)
        _ensure_capacity(event, required_places)
        attendee = _create_attendee(
            event=event,
            user=cleaned_data['user'],
            email=cleaned_data['email'],
            anonymous=cleaned_data['anonymous'],
            preferences=registration_preferences(event, cleaned_data),
        )
        avec_attendee = None
        if cleaned_data.get('avec'):
            avec_attendee = _create_attendee(
                event=event,
                user=cleaned_data['avec_user'],
                email=cleaned_data['avec_email'],
                anonymous=cleaned_data['avec_anonymous'],
                preferences=registration_preferences(event, cleaned_data, prefix="avec_"),
                avec_for=attendee,
                duplicate_field='avec_email',
            )

    return EventSignupResult(attendee=attendee, avec_attendee=avec_attendee)


def _ensure_capacity(event, required_places):
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
        raise EventSignupError(
            _("Det finns redan någon anmäld med denna email"),
            field=duplicate_field,
        ) from exc
    except ValidationError as exc:
        raise EventSignupError(exc.messages[0] if exc.messages else str(exc), field=duplicate_field) from exc
