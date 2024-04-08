from django.shortcuts import get_object_or_404
from django.views import generic
from members.models import Member
import logging

from .models import Question
from .vote import handle_vote

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


class ResultsView(generic.DetailView):
    model = Question
    template_name = 'polls/results.html'


def vote(request, question_id):
    question = get_object_or_404(Question, pk=question_id)

    if request.user.is_authenticated:
        user = Member.objects.get(username=request.user.username)
    else:
        user = request.user

    selected_choices = [question.choice_set.get(pk=choice_id) for choice_id in set(request.POST.getlist('choice'))]

    return handle_vote(request, question, user, selected_choices)
