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

# How long one booking may run. A room is lent for an evening or a weekend, not
# for a season, and without a cap one submission can take a room off the calendar
# for as long as the booker likes.
BOOKING_MAX_DURATION = datetime.timedelta(days=7)


def _as_local(moment):
    """Return ``moment`` as an aware datetime in the association's timezone."""
    if not timezone.is_aware(moment):
        return timezone.make_aware(moment, timezone.get_current_timezone())
    return timezone.localtime(moment)


def _absolute_span(start, end):
    """The time actually between two moments, measured through UTC.

    Subtracting two aware datetimes that share a ``tzinfo`` compares their naive
    parts, so a span across a daylight saving change would be an hour out.
    """
    return _as_local(end).astimezone(datetime.UTC) - _as_local(start).astimezone(datetime.UTC)


def _now():
    """The gate's time seam, imported lazily because ``access`` imports this module."""
    from . import access

    return access.now_at()


def booker_label(author):
    """What to call the member behind a booking.

    The full name when the profile has one, because that is the person the board
    is looking for, and the account name only as a fallback: a row reading
    "abbe" next to a user card reading "Albin Bäck" is the same person and looks
    like two.
    """
    return (author.get_full_name() or '').strip() or str(author)


class Room(models.Model):
    name = models.CharField(_('Namn'), max_length=255)
    description = models.TextField(_('Beskrivning'), blank=True)
    code_generation = models.PositiveIntegerField(
        _('Kodgeneration'),
        default=1,
        editable=False,
        help_text=_('Räknas upp varje gång utrymmets kod byts. Koden härleds ur den och kan inte läsas av härifrån.'),
    )
    rotated_at = models.DateTimeField(
        _('Senast bytt'),
        null=True,
        blank=True,
        editable=False,
        help_text=_('När utrymmets kod senast byttes. Gör att den förra koden fungerar en stund till.'),
    )
    bookable_from = models.TimeField(
        _('Bokningsbart från'),
        null=True,
        blank=True,
        help_text=_('Lämna båda tomma för att tillåta bokning dygnet runt. Med tider gäller de varje dag.'),
    )
    bookable_until = models.TimeField(
        _('Bokningsbart till'),
        null=True,
        blank=True,
        help_text=_('En bokning måste börja och sluta inom samma dygn när tider är satta.'),
    )

    class Meta:
        verbose_name = _('Utrymme')
        verbose_name_plural = _('Utrymmen')
        ordering = ('name', 'pk')

    def __str__(self):
        return self.name

    @property
    def has_bookable_hours(self):
        return self.bookable_from is not None and self.bookable_until is not None

    def clean(self):
        super().clean()
        errors = {}
        window = (self.bookable_from is not None, self.bookable_until is not None)
        if window[0] != window[1]:
            errors['bookable_until' if window[0] else 'bookable_from'] = _(
                'Ange både start och slut för bokningsbara tider, eller lämna båda tomma.'
            )
        elif self.has_bookable_hours and self.bookable_from >= self.bookable_until:
            errors['bookable_until'] = _('Sluttiden måste vara efter starttiden.')
        if errors:
            raise ValidationError(errors)

    def rotate_code(self, at=None):
        """Move to the next code for this room and end the unlocks it granted.

        The counter is bumped in the database rather than in Python, so two
        rotations racing each other cannot both read the same generation and
        write the same value back.
        """
        Room.objects.filter(pk=self.pk).update(
            code_generation=F('code_generation') + 1,
            rotated_at=at or timezone.now(),
        )
        self.refresh_from_db(fields=['code_generation', 'rotated_at'])
        return self.code_generation


class Closure(models.Model):
    """A period when a room cannot be booked, for example a renovation.

    A closure blocks new bookings and is listed on the room page, so a visitor
    who is looking at the calendar sees why the room is unavailable instead of
    being refused after filling in the form. It does not touch bookings that were
    already made inside it: the board closes a period because something is
    happening to the room, and silently deleting somebody's booking would be a
    worse answer than telling them.
    """

    room = models.ForeignKey(
        Room,
        verbose_name=_('Utrymme'),
        on_delete=models.CASCADE,
        related_name='closures',
    )
    start = models.DateTimeField(_('Stängt från'))
    end = models.DateTimeField(_('Stängt till'))
    description = models.CharField(
        _('Beskrivning'),
        max_length=255,
        blank=True,
        help_text=_('Visas för besökare, till exempel vad som gör att utrymmet är stängt.'),
    )

    class Meta:
        verbose_name = _('Stängd period')
        verbose_name_plural = _('Stängda perioder')
        ordering = ('start', 'pk')
        constraints = [
            models.CheckConstraint(
                condition=Q(end__gt=F('start')),
                name='closure_end_after_start',
            ),
        ]

    def __str__(self):
        start = timezone.localtime(self.start).strftime('%Y-%m-%d %H:%M') if self.start else '-'
        end = timezone.localtime(self.end).strftime('%Y-%m-%d %H:%M') if self.end else '-'
        return f'{self.room.name}: {start} - {end}'

    def clean(self):
        super().clean()
        if self.start and self.end and self.end <= self.start:
            raise ValidationError({'end': _('Sluttiden måste vara efter starttiden.')})


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
            self.booker_name = booker_label(self.author)
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
            return booker_label(self.author)
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

        if self.start and self.end and _absolute_span(self.start, self.end) > BOOKING_MAX_DURATION:
            errors['end'] = _('En bokning kan vara i högst en vecka.')

        if self.author_id is None and not (self.booker_name or '').strip():
            errors['booker_name'] = _('Ange namnet på den som bokar.')

        # The hours rule is checked on the attached room rather than on a saved
        # one: an admin can create a room and its bookings in a single submission,
        # and the parent has no primary key yet, so a check that waited for one
        # would let an overnight booking through on a room with a daily window.
        if not errors and self.start and self.end:
            hours_error = self._bookable_hours_error()
            if hours_error:
                errors['start'] = hours_error

        if not errors and self.room_id and self.start and self.end:
            if Closure.objects.filter(
                room_id=self.room_id,
                start__lt=self.end,
                end__gt=self.start,
            ).exists():
                errors['start'] = _('Utrymmet är stängt under en del av den tiden.')
            else:
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

    def _bookable_hours_error(self):
        """Complain when a room with bookable hours is asked for outside them.

        The window is a daily one, so a booking inside it has to start and end on
        the same local day as well: an 08:00 to 22:00 room would otherwise take a
        36-hour booking that runs straight through the closed night, which is the
        thing the window exists to prevent. A room that should be bookable across
        days leaves its hours empty.
        """
        room = self.room
        if not room.has_bookable_hours:
            return None
        local_start = _as_local(self.start)
        local_end = _as_local(self.end)
        outside = (
            local_start.time() < room.bookable_from
            or local_start.time() > room.bookable_until
            or local_end.time() < room.bookable_from
            or local_end.time() > room.bookable_until
            or local_start.date() != local_end.date()
        )
        if not outside:
            return None
        return _('Utrymmet kan bara bokas mellan %(from)s och %(until)s samma dag.') % {
            'from': room.bookable_from.strftime('%H:%M'),
            'until': room.bookable_until.strftime('%H:%M'),
        }


class BookingSettings(models.Model):
    """Singleton with the association-wide booking configuration.

    The codes themselves are not here: each room carries its own generation, and
    a room's code is derived from the server secret, the room and that
    generation. What is association-wide is how a visitor is told to get a code
    at all, which is `code_instructions`.
    """

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

    @classmethod
    def get_solo(cls):
        settings, _ = cls.objects.get_or_create(pk=1)
        return settings
