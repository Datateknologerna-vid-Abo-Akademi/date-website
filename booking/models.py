from django.db import models
from django.utils.translation import gettext_lazy as _
from django.utils.timezone import now
from django.conf import settings

# Create your models here.
class Room(models.Model):
    name = models.CharField(_('Namn'), max_length=255, blank=False)
    booking_date_start = models.DateTimeField(_('Startdatum'), default=now)
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    created_time = models.DateTimeField(_('Skapad'), default=now)
