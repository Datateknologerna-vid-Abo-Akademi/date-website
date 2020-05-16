import logging

from django.db import models
from ckeditor.fields import RichTextField
from django.utils.translation import ugettext_lazy as _

logger = logging.getLogger('date')
# Create your models here.

class AdUrl(models.Model):
    ad_url = models.CharField(_('URL'), max_length=255, blank=False)

    def __str__(self):
        return self.ad_url

class IgUrl(models.Model):
    url = models.CharField(_('URL'), max_length=255, blank=False)
    shortcode = models.CharField(_('SHORTCODE'), max_length=255, blank=False)

    def __str__(self):
        return self.url