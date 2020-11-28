from django.db import models
from django.utils.translation import ugettext_lazy as _
from ckeditor.fields import RichTextField
from django.utils import timezone
import datetime


class Blog(models.Model):
    title = models.CharField(_('Titel'), max_length=255, blank=False)
    pub_date = models.DateTimeField(_('Publicera'), default=timezone.now)
    body = RichTextField(_('Innehåll'), blank=True)


    def summary(self):
        return self.body[:100]

    def was_published_recently(self):
        return (self.pub_date >= timezone.now() - datetime.timedelta(days=1) and self.pub_date <= timezone.now())

    def __str__(self):
        return self.title

class Comment(models.Model):
    user = models.CharField(_('Användare'), max_length=255, blank=False)
    blog = models.ForeignKey(Blog, on_delete=models.CASCADE)
    text = RichTextField(_('Kommentar'), blank=False)
    pub_date = models.DateTimeField(_('Publicerad'), auto_now_add=True)

    def contains_traces_of_nuts(self):
        return "nuts" in self.text
