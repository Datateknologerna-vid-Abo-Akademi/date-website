import logging

from django.db import models

logger = logging.getLogger('date')


# Create your models here.

class AdUrl(models.Model):
    ad_url = models.URLField(max_length=255, blank=False)
    company_url = models.URLField(max_length=255, blank=True)

    def __str__(self):
        return self.ad_url
