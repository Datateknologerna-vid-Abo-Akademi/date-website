from django.db import transaction
from django.shortcuts import render, HttpResponseRedirect
from django.db.models import F
from django.urls import reverse

from members.models import ORDINARY_MEMBER
from polls.models import MEMBERS_ONLY, ORDINARY_MEMBERS_ONLY, VOTE_MEMBERS_ONLY, ANYONE

ERROR_MESSAGES = {
    'not_logged_in': "Logga in för att rösta.",
    'already_voted': "Du har redan röstat.",
    'no_choice': "Du valde inget alternativ.",
    'vote_ended': "Röstandet har avslutats.",
    'not_authorized': "Du inte är röstberättigad.",
    'single_choice': "Endast ett val är tillåtet.",
}


def handle_selected_choices(question, selected_choices, user):
    with transaction.atomic():
        for choice in selected_choices:
            choice.votes = F("votes") + 1
            choice.save()
        if user.is_authenticated:
            question.voters.add(user)


def single_choice_multiple_selected(request, question, selected_choices):
    return not question.multiple_choice and len(selected_choices) > 1


def vote_ended(request, question):
    return question.end_vote


def is_user_authorized_to_vote(question, user):
    if question.voting_options == ANYONE:
        return True

    if question.voting_options == MEMBERS_ONLY and user.is_authenticated:
        return True

    if question.voting_options == ORDINARY_MEMBERS_ONLY and user.membership_type == ORDINARY_MEMBER:
        return True

    if (question.voting_options == VOTE_MEMBERS_ONLY and
            user.membership_type == ORDINARY_MEMBER and
            user.get_active_subscription() is not None):
        return True

    return False


def user_has_voted(request, question, user):
    return question.voters.filter(username=user.username).exists()


def validate_vote(request, question, user, selected_choices):
    if vote_ended(request, question):
        return ERROR_MESSAGES['vote_ended']

    if not selected_choices:
        return ERROR_MESSAGES['no_choice']

    if single_choice_multiple_selected(request, question, selected_choices):
        return ERROR_MESSAGES['single_choice']

    if is_user_authorized_to_vote(question, user):
        if user_has_voted(request, question, user) and question.voting_options != ANYONE:
            return ERROR_MESSAGES['already_voted']
    else:
        return ERROR_MESSAGES['not_authorized']

    return None


def handle_vote(request, question, user, selected_choices):
    error_message = validate_vote(request, question, user, selected_choices)

    if error_message:
        return render(request, 'polls/detail.html', {
            'question': question,
            'error_message': error_message,
        })

    handle_selected_choices(question, selected_choices, user)
    return HttpResponseRedirect(reverse('polls:results', args=(question.id,)))
