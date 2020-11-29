import logging

from ckeditor.fields import RichTextField
from django.db import models
from django.utils import timezone
from django.utils.translation import ugettext_lazy as _
from polls.models import Question

logger = logging.getLogger('date')

POST_SLUG_MAX_LENGTH = 50


class Candidate(models.Model):
    img_url = models.URLField(_('Bild URL'), max_length=255, blank=True)
    title = models.CharField(_('Titel'), max_length=255, blank=False)
    content = RichTextField(_('Innehåll'), blank=True)
    published = models.BooleanField(_('Publicera'), default=True)
    slug = models.SlugField(_('Slug'), unique=True, allow_unicode=False, max_length=POST_SLUG_MAX_LENGTH)
    poll_url = models.URLField(_('Poll URL'), max_length=255, blank=False)

    class Meta:
        verbose_name = _('Lucia')
        verbose_name_plural = _('Lucian')
        ordering = ('id',)

    def __str__(self):
        return self.title