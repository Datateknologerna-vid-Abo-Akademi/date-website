from django.apps import apps
from django.db import transaction
from django.db.models import F
from django.http import HttpResponseRedirect
from django.shortcuts import render
from django.urls import reverse

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
    'not_present': "Du måste vara närvarande på mötet för att rösta.",
    'invalid_choice': "Du valde ett alternativ som inte hör till frågan.",
}


def voter_is_present(question, user):
    """Whether the poll's meeting lets this voter in, if it has a meeting at all.

    A question is an ordinary poll unless an ``AttendancePoll`` row attaches it
    to a meeting, so a question with no attachment, and every question on an
    association that does not install ``attendance``, answer True here and keep
    the vote rules they had before.

    The lookup is guarded because ``polls`` is installed by every association
    while only DaTe installs ``attendance``: ``Question.attendance_poll`` does
    not exist anywhere else, and an unguarded import or access would break those
    variants.

    An anonymous voter is not present, because a member is the only thing
    ``is_attendee_present`` can look up in the meeting's changes.
    """
    if not apps.is_installed('attendance'):
        return True

    attendance_poll = getattr(question, 'attendance_poll', None)
    if attendance_poll is None:
        return True

    if not user.is_authenticated:
        return False

    return attendance_poll.event.is_attendee_present(user)


def selected_choices_belong_to_question(question, selected_choices):
    """Every posted choice has to be an answer to the question being voted on.

    The ids come straight from the POST, so a crafted submission can name the
    choices of another poll and inflate that poll's counters. A value that is
    not an id at all is refused the same way rather than being handed to the
    database, where it would raise instead of answering.
    """
    try:
        posted_ids = {int(choice_id) for choice_id in selected_choices}
    except TypeError, ValueError:
        return False

    # Counted rather than fetched: the ids are only compared, and a question can
    # hold many more choices than one vote names.
    return Choice.objects.filter(question=question, id__in=posted_ids).count() == len(posted_ids)


def handle_selected_choices(question, selected_choices, user):
    with transaction.atomic():
        # Scoped to the question so the write path stays safe even if a caller
        # ever reaches it without validate_vote() in front of it.
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


def validate_vote(request, question, user, selected_choices):
    if vote_ended(request, question):
        return ERROR_MESSAGES['vote_ended']

    if not selected_choices:
        return ERROR_MESSAGES['no_choice']

    if single_choice_multiple_selected(request, question, selected_choices):
        return ERROR_MESSAGES['single_choice']

    if not required_multiple_choices_matches_selected(question, selected_choices):
        return ERROR_MESSAGES['required_multiple_choices'] % question.required_multiple_choices

    if not selected_choices_belong_to_question(question, selected_choices):
        return ERROR_MESSAGES['invalid_choice']

    if is_user_authorized_to_vote(question, user):
        if user_has_voted(request, question, user) and question.voting_options != ANYONE:
            return ERROR_MESSAGES['already_voted']
    else:
        return ERROR_MESSAGES['not_authorized']

    # Deliberately last: a voter the poll refuses on its own terms hears that,
    # rather than being told they are not in the room.
    if not voter_is_present(question, user):
        return ERROR_MESSAGES['not_present']

    return None


def handle_vote(request, question, user, selected_choices):
    error_message = validate_vote(request, question, user, selected_choices)

    if error_message:
        return render(
            request,
            'polls/detail.html',
            {
                'question': question,
                'error_message': error_message,
            },
        )

    handle_selected_choices(question, selected_choices, user)
    return HttpResponseRedirect(reverse('polls:results', args=(question.id,)))
