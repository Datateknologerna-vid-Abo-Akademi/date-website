import logging

from django.db import models
from django.utils.translation import ugettext_lazy as _

logger = logging.getLogger('date')
# Create your models here.

class AdUrl(models.Model):
    ad_url = models.CharField(_('URL'), max_length=255, blank=False)

    def __str__(self):
        return self.ad_url
