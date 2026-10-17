import logging

from django.shortcuts import get_object_or_404
from django.views import generic

from members.models import Member

from .models import Question
from .vote import attendance_requirement, handle_vote

logger = logging.getLogger('date')


class IndexView(generic.ListView):
    template_name = 'polls/index.html'
    context_object_name = 'latest_question_list'

    def get_queryset(self):
        """Return the last five published questions."""
        return Question.objects.published().order_by('-pub_date')[:5]


class DetailView(generic.DetailView):
    model = Question
    template_name = 'polls/detail.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # What the page needs to tell a voter about the meeting, if this poll has
        # one. The vote check reads the same helper, so the two cannot disagree.
        context['attendance_requirement'] = attendance_requirement(self.object, self.request.user)
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

    selected_choices = request.POST.getlist('choice')

    return handle_vote(request, question, user, selected_choices)
