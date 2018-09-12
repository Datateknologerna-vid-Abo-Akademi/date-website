import logging

from ckeditor.fields import RichTextField
from django.db import models
from django.utils import timezone
from django.utils.translation import ugettext_lazy as _
from django.urls import reverse
from core.functions import days_hence

logger = logging.getLogger('date')

POST_SLUG_MAX_LENGTH = 50


class Event(models.Model):
    title = models.CharField(_('Titel'), max_length=255, blank=False)
    content = RichTextField(_('Innehåll'), blank=True)
    event_date_start = models.DateTimeField(_('Startdatum'), default=timezone.now)
    event_date_end = models.DateTimeField(_('Slutdatum'), default=timezone.now)
    event_max_participants = models.IntegerField(_('Maximal antal deltagare'), null=True, blank=True)
    sign_up = models.BooleanField(_('Anmälning'), default=True)
    sign_up_members = models.DateTimeField(_('Anmälan öppnas (medlemmar)'), null=True, blank=True, default=timezone.now)
    sign_up_others = models.DateTimeField(_('Anmälan öppnas (övriga)'), null=True, blank=True, default=timezone.now)
    sign_up_deadline = models.DateTimeField(_('Anmälningen stängs'), default=days_hence(7))
    sign_up_cancelling = models.BooleanField(_('Avanmälning'), default=True)
    sign_up_cancelling_deadline = models.DateTimeField(_('Avanmälningen stängs'), default=days_hence(5))
    author = models.ForeignKey('members.Member', on_delete=models.CASCADE)
    created_time = models.DateTimeField(_('Skapad'), default=timezone.now)
    published_time = models.DateTimeField(_('Publicerad'), editable=False, null=True, blank=True)
    modified_time = models.DateTimeField(_('Modifierad'), editable=False, null=True, blank=True)
    published = models.BooleanField(_('Publicera'), default=True)
    slug = models.SlugField(_('Slug'), unique=True, allow_unicode=False, max_length=POST_SLUG_MAX_LENGTH)

    class Meta:
        verbose_name = _('evenemang')
        verbose_name_plural = _('evenemanger')
        ordering = ('id',)

    def __str__(self):
        return self.title

    def publish(self):
        self.published_time = timezone.now()
        self.published = True
        self.save()

    def unpublish(self):
        self.published = False
        self.save()

    def update(self):
        self.modified_time = timezone.now()
        self.save()

    def get_link(self):
        pass
        #return reverse('article-detail', args=[self.slug])
