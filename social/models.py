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