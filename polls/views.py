from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.views import generic
from django.db.models import F
from members.models import Member
import logging

from .models import Choice, Question, Vote

logger = logging.getLogger('date')

class IndexView(generic.ListView):
    template_name = 'polls/index.html'
    context_object_name = 'latest_question_list'

    def get_queryset(self):
        """Return the last five published questions."""
        return Question.objects.order_by('-pub_date')[:5]


class DetailView(generic.DetailView):
    model = Question
    template_name = 'polls/detail.html'


class ResultsView(generic.DetailView):
    model = Question
    template_name = 'polls/results.html'

def vote(request, question_id):

    user = None
    if request.user.is_authenticated:
        user = Member.objects.get(username=request.user.username)
    logger.info(request.user)

    question = get_object_or_404(Question, pk=question_id)
    try:
        selected_choice = question.choice_set.get(pk=request.POST['choice'])
    except (KeyError, Choice.DoesNotExist):
        # Redisplay the question voting form.
        return render(request, 'polls/detail.html', {
            'question': question,
            'error_message': question.voters.values('username'),#"Du valde inget alternativ.",
        })
    else:
        if question.members_only:
            # checks if user is a member
            if request.user.is_authenticated and not question.voters.filter(username=request.user.username).exists():
                selected_choice.votes = F("votes") + 1
                selected_choice.save()
                user = Member.objects.get(username=request.user.username)
                question.voters.add(user)
                logger.info("is just member")
        elif question.ordinary_members_only:
            # checks if user is ordinary member
            if request.user.is_authenticated and not question.voters.filter(username=request.user.username).exists() and user.membership_type == 2:
                selected_choice.votes = F("votes") + 1
                selected_choice.save()
                user = Member.objects.get(username=request.user.username)
                question.voters.add(user)
                logger.info("ordinary member")
        # anyone can vote
        else:
            logger.info("voted")
            selected_choice.votes = F("votes") + 1
            selected_choice.save()
        # Always return an HttpResponseRedirect after successfully dealing
        # with POST data. This prevents data from being posted twice if a
        # user hits the Back button.
        return HttpResponseRedirect(reverse('polls:results', args=(question.id,)))