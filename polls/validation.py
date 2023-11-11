from django.db import transaction
from django.shortcuts import render, HttpResponseRedirect
from django.db.models import F
from django.urls import reverse

from members.models import ORDINARY_MEMBER

ERROR_MESSAGES = {
    'not_logged_in': "Logga in för att rösta.",
    'already_voted': "Du har redan röstat.",
    'no_choice': "Du valde inget alternativ.",
    'vote_ended': "Röstandet har avslutats.",
    'not_authorized': "Du inte är röstberättigad.",
    'single_choice': "Ändast ett val är tillåtet.",
}


def render_error(request, question, error_message):
    return render(request, 'polls/detail.html', {
        'question': question,
        'error_message': error_message,
    })


def handle_selected_choices(question, selected_choices, user):
    with transaction.atomic():
        for choice in selected_choices:
            choice.votes = F("votes") + 1
            choice.save()
        if user:
            question.voters.add(user)


def members_question(question):
    return question.members_only or question.ordinary_members_only or question.vote_members_only


def get_selected_choices(request, question):
    return [question.choice_set.get(pk=choice_id) for choice_id in set(request.POST.getlist('choice'))]


def single_choice_multiple_selected(request, question, selected_choices):
    return not question.multiple_choice and len(selected_choices) > 1


def vote_ended(request, question):
    return question.end_vote


def members_only_and_not_authenticated(request, question, user):
    if members_question(question) and not user.is_authenticated:
        return render_error(request, question, ERROR_MESSAGES['not_logged_in'])


def can_member_vote(question, user):
    if not user.is_authenticated:
        return False

    if question.members_only:
        return True

    if question.ordinary_members_only and user.membership_type == ORDINARY_MEMBER:
        return True

    if question.vote_members_only and user.membership_type == ORDINARY_MEMBER:
        return user.get_active_subscription() is not None

    return False


def user_has_voted(request, question, user):
    return question.voters.filter(username=user.username).exists()


def validate_and_handle_vote(request, question, user):
    selected_choices = get_selected_choices(request, question)

    if vote_ended(request, question):
        return render_error(request, question, ERROR_MESSAGES['vote_ended'])

    if not selected_choices:
        return render_error(request, question, ERROR_MESSAGES['no_choice'])

    if single_choice_multiple_selected(request, question, selected_choices):
        return render_error(request, question, ERROR_MESSAGES['single_choice'])

    if not members_question:
        handle_selected_choices(question, selected_choices, user=None)
        return HttpResponseRedirect(reverse('polls:results', args=(question.id,)))

    if members_only_and_not_authenticated(request, question, user):
        return render_error(request, question, ERROR_MESSAGES['not_logged_in'])

    if can_member_vote(question, user):
        if user_has_voted(request, question, user):
            return render_error(request, question, ERROR_MESSAGES['already_voted'])

        handle_selected_choices(question, selected_choices, user)
        return HttpResponseRedirect(reverse('polls:results', args=(question.id,)))
    else:
        return render_error(request, question, ERROR_MESSAGES['not_authorized'])
