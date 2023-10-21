import logging

from django.db import models
from django.utils.translation import gettext_lazy as _

logger = logging.getLogger('date')

# Create your models here.

class IgUrl(models.Model):
    url = models.CharField(_('URL'), max_length=255, blank=False)
    shortcode = models.CharField(_('SHORTCODE'), max_length=255, blank=False)

    def __str__(self):
        return self.url


class Harassment(models.Model):
    email = models.EmailField(_('Email'), max_length=255, blank=True, null=True)
    message = models.TextField(_('Beskrivning av händelsen'), blank=False, max_length=1500)

    def __str__(self):
        return self.message
