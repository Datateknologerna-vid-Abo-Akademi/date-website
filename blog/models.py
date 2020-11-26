from ckeditor.fields import RichTextField
from django.db import models
from django.utils import timezone
from django.utils.translation import ugettext_lazy as _
import datetime

class Blog(models.Model):
    title = models.CharField(_('Titel'), max_length=255, blank=False)
    pub_date = models.DateTimeField(_('Publicerad'), editable=False, null=True, blank=True)
    body = RichTextField(_('Innehåll'), blank=True)

    def summary(self):
        return self.body[:100]

    def was_published_recently(self):
        return self.pub_date >= timezone.now() - datetime.timedelta(days=1) and self.pub_date <= timezone.now()

    def __str__(self):
        return self.title


class Comment(models.Model):
    blog = models.ForeignKey(Blog, on_delete=models.CASCADE)
    user = models.CharField(_('Användare'), max_length=255, blank=False)
    text = RichTextField(_('Innehåll'), blank=True)
    pub_date = models.DateTimeField(_('Publicerad'), editable=False, null=True, blank=True)
