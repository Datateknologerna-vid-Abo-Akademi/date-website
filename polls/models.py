import logging

from django.db import models
from django.utils.translation import gettext_lazy as _
from members.models import Member

logger = logging.getLogger('date')

ANYONE = 1
MEMBERS_ONLY = 2
ORDINARY_MEMBERS_ONLY = 3
VOTE_MEMBERS_ONLY = 4

VOTING_OPTIONS = [
    (ANYONE, _('Vem som helst')),
    (MEMBERS_ONLY, _('Endast medlemmar')),
    (ORDINARY_MEMBERS_ONLY, _('Endast ordinarie medlemmar')),
    (VOTE_MEMBERS_ONLY, _('Endast röstberättigade medlemmar')),
]


class Question(models.Model):
    question_text = models.CharField(max_length=200)
    pub_date = models.DateTimeField(auto_now_add=True)
    published = models.BooleanField(_('Publicera'), default=True)
    show_results = models.BooleanField(_('Visa resultat'), default=False)
    end_vote = models.BooleanField(_('Avsluta röstande'), default=False)
    multiple_choice = models.BooleanField(_('Flerval'), default=False)
    required_multiple_choices = models.IntegerField(_('Antal flerval som krävs'), blank=True, null=True)
    voting_options = models.IntegerField(_('Valmöjligheter'), choices=VOTING_OPTIONS, default=ANYONE)
    voters = models.ManyToManyField(Member, through="Vote", related_name='voters')

    class Meta:
        verbose_name = _('Fråga')
        verbose_name_plural = _('Frågor')

    def __str__(self):
        return self.question_text

    def get_total_votes(self):
        count_sum = 0
        for choice in Choice.objects.filter(question=self):
            count_sum += choice.votes
        return count_sum


class Choice(models.Model):
    question = models.ForeignKey(Question, on_delete=models.CASCADE)
    choice_text = models.CharField(max_length=200)
    votes = models.IntegerField(default=0)
    
    class Meta:
        verbose_name = _('Val')
        verbose_name_plural = _('Val')

    def __str__(self):
        return self.choice_text

    def get_vote_percentage(self):
        return int((self.votes / self.question.get_total_votes())*10**2)


class Vote(models.Model):
    question = models.ForeignKey(Question, on_delete=models.CASCADE)
    user = models.ForeignKey(Member, on_delete=models.CASCADE)
    voted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _('Röstare')
        verbose_name_plural = _('Röstare')

    def __str__(self):
        return self.user.first_name + " " + self.user.last_name
