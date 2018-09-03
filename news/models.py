import logging

from django.db import models
from django.utils import timezone
from django.utils.translation import ugettext_lazy as _

logger = logging.getLogger('date')


class Post(models.Model):
    title = models.CharField(_('Titel'), max_length=255, blank=False)
    content = models.TextField(_('Innehåll'), blank=True)
    author = models.ForeignKey('members.Member', on_delete=models.CASCADE)
    created_time = models.DateTimeField(_('Skapad'), default=timezone.now)
    published_time = models.DateTimeField(_('Publicerad'), editable=False, null=True, blank=True)
    modified_time = models.DateTimeField(_('Modifierad'), editable=False, null=True, blank=True)
    published = models.BooleanField(_('Publicera'), default=True)

    class Meta:
        verbose_name = _('nyhet')
        verbose_name_plural = _('nyheter')
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
