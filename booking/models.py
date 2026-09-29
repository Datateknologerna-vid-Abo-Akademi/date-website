from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import F, Q
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


class Room(models.Model):
    name = models.CharField(_('Namn'), max_length=255)
    description = models.TextField(_('Beskrivning'), blank=True)
    is_active = models.BooleanField(
        _('Aktiv'),
        default=True,
        help_text=_('Endast aktiva utrymmen visas för besökare på webbplatsen.'),
    )

    class Meta:
        verbose_name = _('Utrymme')
        verbose_name_plural = _('Utrymmen')
        ordering = ('name', 'pk')

    def __str__(self):
        return self.name


class Booking(models.Model):
    room = models.ForeignKey(
        Room,
        verbose_name=_('Utrymme'),
        on_delete=models.CASCADE,
        related_name='bookings',
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_('Bokare'),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='room_bookings',
    )
    booker_name = models.CharField(_('Namn'), max_length=255, blank=True)
    booker_email = models.EmailField(_('E-post'), blank=True)
    start = models.DateTimeField(_('Starttid'))
    end = models.DateTimeField(_('Sluttid'))
    description = models.CharField(_('Beskrivning'), max_length=400, blank=True)
    created = models.DateTimeField(_('Skapad'), default=timezone.now, editable=False)

    class Meta:
        verbose_name = _('Bokning')
        verbose_name_plural = _('Bokningar')
        ordering = ('start', 'pk')
        constraints = [
            models.CheckConstraint(
                condition=Q(end__gt=F('start')),
                name='booking_end_after_start',
            ),
        ]

    def __str__(self):
        start = timezone.localtime(self.start).strftime('%Y-%m-%d %H:%M') if self.start else '-'
        end = timezone.localtime(self.end).strftime('%Y-%m-%d %H:%M') if self.end else '-'
        return f'{self.room.name}: {start} - {end}'

    @property
    def is_external(self):
        """An external booking has no website account behind it."""
        return self.author_id is None

    @property
    def booker_display(self):
        if self.author_id:
            return str(self.author)
        return self.booker_name or str(_('Extern bokning'))

    def clean(self):
        super().clean()
        errors = {}

        if self.start and self.end and self.end <= self.start:
            errors['end'] = _('Sluttiden måste vara efter starttiden.')

        if self.author_id is None and not (self.booker_name or '').strip():
            errors['booker_name'] = _('Ange namnet på den som bokar.')

        if not errors and self.room_id and self.start and self.end:
            overlapping = Booking.objects.filter(
                room_id=self.room_id,
                start__lt=self.end,
                end__gt=self.start,
            )
            if self.pk:
                overlapping = overlapping.exclude(pk=self.pk)
            if overlapping.exists():
                errors['start'] = _('Utrymmet är redan bokat under denna tid.')

        if errors:
            raise ValidationError(errors)


class BookingSettings(models.Model):
    """Singleton with the association-wide booking configuration.

    There is no stored booking code: the code is derived from the server secret
    and the current time slot, so it cannot be set or read back here.
    """

    ROTATION_DAILY = 'daily'
    ROTATION_WEEKLY = 'weekly'
    ROTATION_MONTHLY = 'monthly'
    ROTATION_CHOICES = [
        (ROTATION_DAILY, _('Dagligen')),
        (ROTATION_WEEKLY, _('Veckovis')),
        (ROTATION_MONTHLY, _('Månadsvis')),
    ]

    rotation_period = models.CharField(
        _('Kodens rotationsperiod'),
        max_length=8,
        choices=ROTATION_CHOICES,
        default=ROTATION_WEEKLY,
        help_text=_('Hur ofta bokningskoden byts ut. Koden genereras automatiskt och kan inte ställas in manuellt.'),
    )

    class Meta:
        verbose_name = _('Bokningsinställningar')
        verbose_name_plural = _('Bokningsinställningar')

    def __str__(self):
        return str(_('Bokningsinställningar'))

    @classmethod
    def get_solo(cls):
        settings, _ = cls.objects.get_or_create(pk=1)
        return settings
