import logging

from django.shortcuts import get_object_or_404
from django.views import generic

from members.models import Member

from .models import ANYONE, Question
from .vote import ERROR_MESSAGES, handle_vote, user_has_voted

logger = logging.getLogger('date')


class IndexView(generic.ListView):
    template_name = 'polls/index.html'
    context_object_name = 'latest_question_list'

    def get_queryset(self):
        """Return the last five published questions."""
        return Question.objects.filter(published=True).order_by('-pub_date')[:5]


class DetailView(generic.DetailView):
    model = Question
    template_name = 'polls/detail.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        if user.is_authenticated:
            try:
                user = Member.objects.get(username=user.username)
            except Member.DoesNotExist:  # pragma: no cover - fallback if user deleted
                pass
        if (
            user.is_authenticated
            and self.object.voting_options != ANYONE
            and user_has_voted(self.request, self.object, user)
        ):
            context["already_voted"] = True
            context["already_voted_message"] = ERROR_MESSAGES["already_voted"]
        return context


class ResultsView(generic.DetailView):
    model = Question
    template_name = 'polls/results.html'


def vote(request, question_id):
    question = get_object_or_404(Question, pk=question_id)

    if request.user.is_authenticated:
        user = Member.objects.get(username=request.user.username)
    else:
        user = request.user

    selected_choices = [choice_id for choice_id in set(request.POST.getlist('choice'))]

    return handle_vote(request, question, user, selected_choices)
