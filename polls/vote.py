from typing import Any, NamedTuple

from django.apps import apps
from django.db import transaction
from django.db.models import F
from django.http import HttpResponseRedirect
from django.shortcuts import render
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from members.models import ORDINARY_MEMBER
from polls.models import ANYONE, MEMBERS_ONLY, ORDINARY_MEMBERS_ONLY, VOTE_MEMBERS_ONLY, Choice

ERROR_MESSAGES = {
    'not_logged_in': "Logga in för att rösta.",
    'already_voted': "Du har redan röstat.",
    'no_choice': "Du valde inget alternativ.",
    'vote_ended': "Röstandet har avslutats.",
    'not_authorized': "Du inte är röstberättigad.",
    'single_choice': "Endast ett val är tillåtet.",
    'required_multiple_choices': "Du måste välja exakt %s alternativ.",
    # Both a signed-in member who is not in the room and an anonymous visitor
    # who cannot be matched to one read this as addressed to themselves.
    'not_present': _("Du måste vara närvarande på mötet för att rösta."),
    'invalid_choice': _("Du valde ett alternativ som inte hör till frågan."),
}


class AttendanceRequirement(NamedTuple):
    """What a room-only poll needs from the visitor reading the page.

    ``event`` is the meeting the poll is attached to, and the page names it and
    links to its check-in page. ``is_signed_in`` keeps the page from offering
    that link to a guest, who has no member the meeting's changes can be looked
    up by and therefore cannot vote however many times they check in.
    ``is_present`` is the same answer ``voter_is_present()`` acts on.
    """

    event: Any
    is_signed_in: bool
    is_present: bool


def attendance_requirement(question, user):
    """The meeting a poll is attached to and whether this voter is in it, or None.

    None means the poll is an ordinary one: either the association has no
    attendance app, or no AttendancePoll row attaches this question to a meeting.

    The lookup is guarded because ``polls`` is installed by every association
    while only DaTe installs ``attendance``: ``Question.attendance_poll`` does
    not exist anywhere else, and an unguarded import or access would break those
    variants. This function is the one definition of the attachment, so the poll
    page and the vote check cannot disagree about the room.

    An anonymous voter is not present, because a member is the only thing
    ``is_attendee_present`` can look up in the meeting's changes.
    """
    if not apps.is_installed('attendance'):
        return None

    attendance_poll = getattr(question, 'attendance_poll', None)
    if attendance_poll is None:
        return None

    is_signed_in = user.is_authenticated

    return AttendanceRequirement(
        event=attendance_poll.event,
        is_signed_in=is_signed_in,
        is_present=is_signed_in and attendance_poll.event.is_attendee_present(user),
    )


def voter_is_present(question, user):
    """Whether the poll's meeting lets this voter in, if it has a meeting at all.

    A question is an ordinary poll unless an ``AttendancePoll`` row attaches it
    to a meeting, so a question with no attachment, and every question on an
    association that does not install ``attendance``, answer True here and keep
    the vote rules they had before.

    Thin over ``attendance_requirement()``, which is also what the poll page
    reads, so what the page says about the room is what the POST enforces.
    """
    requirement = attendance_requirement(question, user)

    return requirement is None or requirement.is_present


def normalize_selected_choice_ids(selected_choices) -> list[int] | None:
    """Parse choice ids once and reject numeric aliases of the same choice."""
    try:
        choice_ids = [int(choice_id) for choice_id in selected_choices]
    except TypeError, ValueError:
        return None

    if len(choice_ids) != len(set(choice_ids)):
        return None

    return choice_ids


def selected_choices_belong_to_question(question, choice_ids: list[int]) -> bool:
    """Every normalized, unique choice id must belong to the question.

    The ids come straight from the POST, so a crafted submission can name the
    choices of another poll and inflate that poll's counters. Counting rather
    than fetching is enough: the ids are only compared, and a question can hold
    many more choices than one vote names.
    """
    return Choice.objects.filter(question=question, id__in=choice_ids).count() == len(choice_ids)


def handle_selected_choices(question, selected_choices, user):
    with transaction.atomic():
        # The caller passes the same normalized, duplicate-free ids that passed
        # validation. Scope the write to the question as a second boundary.
        Choice.objects.filter(question=question, id__in=selected_choices).update(votes=F('votes') + 1)
        if user.is_authenticated:
            question.voters.add(user)


def single_choice_multiple_selected(request, question, selected_choices):
    return not question.multiple_choice and len(selected_choices) > 1


def vote_ended(request, question):
    return question.end_vote


def is_user_authorized_to_vote(question, user):
    if question.voting_options == ANYONE:
        return True

    if not user.is_authenticated:
        return False

    if question.voting_options == MEMBERS_ONLY:
        return True

    if question.voting_options == ORDINARY_MEMBERS_ONLY and user.membership_type.permission_profile == ORDINARY_MEMBER:
        return True

    if (
        question.voting_options == VOTE_MEMBERS_ONLY
        and user.membership_type.permission_profile == ORDINARY_MEMBER
        and user.get_active_subscription() is not None
    ):
        return True

    return False


def user_has_voted(request, question, user):
    return question.voters.filter(username=user.username).exists()


def required_multiple_choices_matches_selected(question, selected_choices):
    if question.required_multiple_choices is None or question.required_multiple_choices <= 0:
        return True

    return len(selected_choices) == question.required_multiple_choices


def _validate_vote(request, question, user, selected_choices):
    if vote_ended(request, question):
        return ERROR_MESSAGES['vote_ended'], None

    if not selected_choices:
        return ERROR_MESSAGES['no_choice'], None

    # Canonical ids are shared by the required-choice count, ownership check and
    # database update, so values such as "1" and "+1" cannot count as two picks.
    choice_ids = normalize_selected_choice_ids(selected_choices)
    if choice_ids is None:
        return ERROR_MESSAGES['invalid_choice'], None

    if single_choice_multiple_selected(request, question, choice_ids):
        return ERROR_MESSAGES['single_choice'], None

    if not required_multiple_choices_matches_selected(question, choice_ids):
        return ERROR_MESSAGES['required_multiple_choices'] % question.required_multiple_choices, None

    if not selected_choices_belong_to_question(question, choice_ids):
        return ERROR_MESSAGES['invalid_choice'], None

    if is_user_authorized_to_vote(question, user):
        if user_has_voted(request, question, user) and question.voting_options != ANYONE:
            return ERROR_MESSAGES['already_voted'], None
    else:
        return ERROR_MESSAGES['not_authorized'], None

    # Deliberately last: a voter the poll refuses on its own terms hears that,
    # rather than being told they are not in the room.
    if not voter_is_present(question, user):
        return ERROR_MESSAGES['not_present'], None

    return None, choice_ids


def validate_vote(request, question, user, selected_choices):
    """Return the validation error, if any, for a submitted choice list."""
    error_message, _ = _validate_vote(request, question, user, selected_choices)
    return error_message


def handle_vote(request, question, user, selected_choices):
    error_message, choice_ids = _validate_vote(request, question, user, selected_choices)

    if error_message:
        return render(
            request,
            'polls/detail.html',
            {
                'question': question,
                'error_message': error_message,
                # The refusal reads as a dead end without it: the template uses
                # this to point the voter at the meeting's check-in page.
                'attendance_requirement': attendance_requirement(question, user),
            },
        )

    assert choice_ids is not None
    handle_selected_choices(question, choice_ids, user)
    return HttpResponseRedirect(reverse('polls:results', args=(question.id,)))
