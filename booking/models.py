import datetime

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import F, Q
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

# The datetime-local input has minute precision and a form takes a moment to
# fill in, so a start a few minutes in the past is not a mistake. A start older
# than this is a wrong date, and the booking would be invisible everywhere the
# page lists upcoming times while still occupying the room in the admin.
BOOKING_PAST_GRACE = datetime.timedelta(minutes=10)


def _now():
    """The gate's time seam, imported lazily because ``access`` imports this module."""
    from . import access

    return access.now_at()


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

    def save(self, *args, **kwargs):
        """Record who booked while the account still exists.

        ``author`` is ``SET_NULL``, so a deleted member's booking would
        otherwise lose its booker and read as a booking without an account.
        The name is only filled in when it is blank, so a name typed by the
        board is never overwritten.
        """
        update_fields = kwargs.get('update_fields')
        if update_fields is not None:
            # Materialised for two reasons: an empty ``update_fields`` means
            # "write nothing", which is Django's own meaning for it, and a
            # generator left in kwargs could not be read a second time.
            update_fields = {*update_fields}
            kwargs['update_fields'] = update_fields
        # The snapshot is filled in only when the save writes the row at all.
        # Filling it in for a save that writes nothing would leave it on the
        # instance, and the next narrow save would then find a name already
        # there, skip the snapshot, and write an author with a blank name.
        writes_row = update_fields is None or bool(update_fields)
        if writes_row and not self.booker_name and self.author_id:
            self.booker_name = str(self.author)
            if update_fields is not None:
                kwargs['update_fields'] = update_fields | {'booker_name'}
        super().save(*args, **kwargs)

    @property
    def is_external(self):
        """Whether the booking has no website account behind it.

        A booking made by a member who later deletes the account lands here
        too, because ``author`` is ``SET_NULL``; ``booker_name`` is snapshotted
        on save, so the name of the person who booked survives either way.
        """
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

        # Checked only for a new booking. A booking that already exists keeps
        # whatever times it has, so the board can still correct a booking whose
        # time has passed without being told the time is invalid.
        if self._state.adding and self.start and self.start < _now() - BOOKING_PAST_GRACE:
            errors['start'] = _('Starttiden kan inte vara i det förflutna.')

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
    and ``code_generation``, a counter that only moves when the board rotates
    the code on purpose. Nothing about the code depends on the clock, so no
    schedule has to run for it to stay correct.
    """

    code_generation = models.PositiveIntegerField(
        _('Kodgeneration'),
        default=1,
        editable=False,
        help_text=_('Räknas upp varje gång koden byts. Koden härleds ur den och kan inte läsas av härifrån.'),
    )
    rotated_at = models.DateTimeField(
        _('Senast bytt'),
        null=True,
        blank=True,
        editable=False,
        help_text=_('När koden senast byttes. Gör att den förra koden fungerar en stund till.'),
    )
    code_instructions = models.TextField(
        _('Så får besökare koden'),
        blank=True,
        help_text=_(
            'Visas offentligt där koden efterfrågas, i stället för standardtexten. Lämna tomt om standardtexten räcker.'
        ),
    )

    class Meta:
        verbose_name = _('Bokningsinställningar')
        verbose_name_plural = _('Bokningsinställningar')

    def __str__(self):
        return str(_('Bokningsinställningar'))

    def rotate_code(self, at=None):
        """Move to the next code and end every existing unlock.

        The counter is bumped in the database rather than in Python, so two
        rotations racing each other cannot both read the same generation and
        write the same value back.
        """
        BookingSettings.objects.filter(pk=self.pk).update(
            code_generation=F('code_generation') + 1,
            rotated_at=at or timezone.now(),
        )
        self.refresh_from_db(fields=['code_generation', 'rotated_at'])
        return self.code_generation

    @classmethod
    def get_solo(cls):
        settings, _ = cls.objects.get_or_create(pk=1)
        return settings
