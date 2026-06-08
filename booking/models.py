from django.db import models
from django.utils.translation import gettext_lazy as _
from django.utils.timezone import now
from django.conf import settings

# Create your models here.
class Room(models.Model):
    name = models.CharField(_('Namn'), max_length=255, blank=False)

    class Meta:
        verbose_name = _('Utrymme')
        verbose_name_plural = _('Utrymmen')
        ordering = ('name',)

class Booking(models.Model):
    room = models.ForeignKey(Room, verbose_name=_('Utrymme'), on_delete=models.CASCADE)
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    created = models.DateTimeField(_('Skapad'), default=now)
    booking_date_start = models.DateTimeField(_('Startdatum'), default=now)
    booking_date_end = models.DateTimeField(_('Slutdatum'), default=now)
    description = models.CharField(_('Beskrivning'), max_length=400, blank=False)

    class Meta:
        verbose_name = _('Bokning')
        verbose_name_plural = _('Bokningar')
        ordering = ('booking_date_start',)

    def __str__(self):
        return f"{self.room.name} - {self.booking_date_start} to {self.booking_date_end}"