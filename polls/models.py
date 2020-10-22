import logging

from django.db import models
from django.utils.translation import ugettext_lazy as _
from django.utils.timezone import now

logger = logging.getLogger('date')

class Question(models.Model):
    question_text = models.CharField(max_length=200)
    pub_date = models.DateTimeField('date published')
    published = models.BooleanField(_('Publicera'), default=True)
    multiple_choice = models.BooleanField(_('Flerval'), default=False)
    members_only = models.BooleanField(_('Endast medlemmar'), default=False)
    def __str__(self):
        return self.question_text

    def publish(self):
        self.published_time = now()
        self.published = True
        self.save()

    def unpublish(self):
        self.published = False
        self.save()

class Choice(models.Model):
    question = models.ForeignKey(Question, on_delete=models.CASCADE)
    choice_text = models.CharField(max_length=200)
    votes = models.IntegerField(default=0)
    def __str__(self):
        return self.choice_text
