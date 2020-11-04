from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.views import generic
from django.db.models import F
from members.models import Member
import logging

from .models import Choice, Question, Vote, RightToVote

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

    choices = None

    if request.user.is_authenticated:
        user = Member.objects.get(username=request.user.username)

    if request.method == 'POST':
        choices = request.POST.getlist('choice')
        
    question = get_object_or_404(Question, pk=question_id)

    try:
        selected_choices = [question.choice_set.get(pk=choice_id) for choice_id in choices]
    except (KeyError, Choice.DoesNotExist):
        # Redisplay the question voting form.
        return render(request, 'polls/detail.html', {
            'question': question,
            'error_message': "Du valde inget alternativ.",
        })
    else:
        if question.end_vote:
             return render(request, 'polls/detail.html', {
            'question': question,
            'error_message': "Röstandet har avslutas.",
        })
        else:
            if question.members_only:
                if request.user.is_authenticated:
                    # checks if user is a member
                    if not question.voters.filter(username=request.user.username).exists():
                        for choice in selected_choices:
                            # Avoid race condition https://docs.djangoproject.com/en/3.1/ref/models/expressions/#avoiding-race-conditions-using-f
                            choice.votes = F("votes") + 1
                            choice.save()
                        question.voters.add(user)
                    else:
                        return render(request, 'polls/detail.html', {
                            'question': question,
                            'error_message': "Du kan inte rösta. Orsaken kan vara att du redan använt din röst eller inte är röstberättigad!",
                        })
                else:
                    return render(request, 'polls/detail.html', {
                        'question': question,
                        'error_message': "Logga in för att rösta.",
                    })

            elif question.ordinary_members_only:
                if request.user.is_authenticated:
                    # checks if user is ordinary member
                    if not question.voters.filter(username=request.user.username).exists() and user.membership_type == 2:
                        for choice in selected_choices:
                            choice.votes = F("votes") + 1
                            choice.save()
                        question.voters.add(user)
                    else:
                        return render(request, 'polls/detail.html', {
                            'question': question,
                            'error_message': "Du kan inte rösta. Orsaken kan vara att du redan använt din röst eller inte är röstberättigad!",
                        })
                else:
                    return render(request, 'polls/detail.html', {
                        'question': question,
                        'error_message': "Logga in för att rösta.",
                    })
            elif question.vote_members_only:
                if request.user.is_authenticated:
                    # checks if user registered voter
                    if not question.voters.filter(username=request.user.username).exists() and user.membership_type == 2 and question.right_to_vote.suffrages.filter(username=request.user.username).exists():
                        for choice in selected_choices:
                            choice.votes = F("votes") + 1
                            choice.save()
                        question.voters.add(user)
                    else:
                        return render(request, 'polls/detail.html', {
                            'question': question,
                            'error_message': "Du kan inte rösta. Orsaken kan vara att du redan använt din röst eller inte är röstberättigad!",
                        })
                else:
                    return render(request, 'polls/detail.html', {
                        'question': question,
                        'error_message': "Logga in för att rösta.",
                    })
            # anyone can vote
            else:
                for choice in selected_choices:
                    choice.votes = F("votes") + 1
                    choice.save()
        # Always return an HttpResponseRedirect after successfully dealing
        # with POST data. This prevents data from being posted twice if a
        # user hits the Back button.
        return HttpResponseRedirect(reverse('polls:results', args=(question.id,)))