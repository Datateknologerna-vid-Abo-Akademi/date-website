import logging

from django.db import models
from django.utils.translation import ugettext_lazy as _
from django.utils.timezone import now
from members.models import Member

logger = logging.getLogger('date')

class Question(models.Model):
    question_text = models.CharField(max_length=200)
    pub_date = models.DateTimeField(auto_now_add=True)
    published = models.BooleanField(_('Publicera'), default=True)
    show_results = models.BooleanField(_('Visa resultat'), default=False)
    multiple_choice = models.BooleanField(_('Flerval'), default=False)
    members_only = models.BooleanField(_('Endast medlemmar'), default=False)
    ordinary_members_only = models.BooleanField(_('Endast ordinarie medlemmar'), default=False)
    vote_members_only = models.BooleanField(_('Endast röstberättigade medlemmar'), default=False)
    voters = models.ManyToManyField(Member, through="Vote", related_name='voters')
    suffrages = models.ManyToManyField(Member, through="Suffrage", related_name='suffrages')
    def __str__(self):
        return self.question_text

class Choice(models.Model):
    question = models.ForeignKey(Question, on_delete=models.CASCADE)
    choice_text = models.CharField(max_length=200)
    votes = models.IntegerField(default=0)
    def __str__(self):
        return self.choice_text
    class Meta:
        verbose_name = _('Val')
        verbose_name_plural = _('Val')

class Vote(models.Model):
    question = models.ForeignKey(Question, on_delete=models.CASCADE)
    user = models.ForeignKey(Member, on_delete=models.CASCADE)
    voted_at = models.DateTimeField(auto_now_add=True)

class Suffrage(models.Model):
    question = models.ForeignKey(Question, on_delete=models.CASCADE)
    user = models.ForeignKey(Member, on_delete=models.CASCADE)
    class Meta:
            verbose_name = _('Röstberättigad medlem')
            verbose_name_plural = _('Röstberättigade medlemmar')
    def __str__(self):
        return self.user.first_name +  " " + self.user.last_name