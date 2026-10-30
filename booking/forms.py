from django import forms
from django.conf import settings
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from . import access
from .models import BOOKING_PAST_GRACE, Booking

BOOKING_DATETIME_FORMAT = '%Y-%m-%dT%H:%M'


def _local_datetime_widget(label):
    """A datetime-local input that keeps the browser value after a reload.

    The field's label goes on as an accessible name too. The room page shows one
    "Tid" label over both datetime inputs, so without this the second of them
    would have no name of its own for a screen reader.
    """
    return forms.DateTimeInput(
        attrs={'type': 'datetime-local', 'aria-label': label},
        format=BOOKING_DATETIME_FORMAT,
    )


def local_datetime_field(label):
    """A DateTimeField wired to the datetime-local widget it renders.

    ``input_formats`` belongs to the field rather than to the widget, so both
    halves are built here: the browser value has to be accepted and a value
    that failed validation still has to come back in the input's own format.
    """
    widget = _local_datetime_widget(label)
    field = forms.DateTimeField(label=label, widget=widget)
    field.input_formats = [BOOKING_DATETIME_FORMAT, *getattr(settings, 'DATETIME_INPUT_FORMATS', ())]
    field.widget.input_formats = field.input_formats
    return field


class BookingCodeForm(forms.Form):
    code = forms.CharField(
        label=_('Bokningskod'),
        max_length=access.BOOKING_CODE_DIGITS,
        widget=forms.TextInput(attrs={'inputmode': 'numeric', 'autocomplete': 'off'}),
    )

    def __init__(self, *args, room, at=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.room = room
        self.at = at

    def clean_code(self):
        code = self.cleaned_data['code']
        if not access.check_code(self.room, code, at=self.at):
            raise forms.ValidationError(_('Fel kod.'))
        return code


class BookingForm(forms.ModelForm):
    start = local_datetime_field(_('Starttid'))
    end = local_datetime_field(_('Sluttid'))
    # Declared rather than taken from the model: the model keeps ``blank=True``
    # so a booking made before the field existed still saves, while every new
    # booking has to say what it is about.
    title = forms.CharField(
        label=_('Titel'),
        max_length=120,
        error_messages={'required': _('Ange en kort titel för bokningen.')},
        help_text=_('Visas offentligt på bokningssidorna. Skriv kort vad bokningen gäller.'),
    )
    description = forms.CharField(
        label=_('Beskrivning'),
        max_length=400,
        required=False,
        widget=forms.Textarea(attrs={'rows': 3}),
        help_text=_('Berätta kort vad utrymmet ska användas till. Endast styrelsen ser detta.'),
    )

    class Meta:
        model = Booking
        fields = ('title', 'start', 'end', 'description')

    def __init__(self, *args, room=None, author=None, **kwargs):
        super().__init__(*args, **kwargs)
        if room is not None:
            self.room = room
        if author is not None:
            self.author = author
        self._initial_start = self.instance.start if self.instance.pk is not None else None
        self._initial_end = self.instance.end if self.instance.pk is not None else None
        if self.instance.pk is None:
            # The model refuses a new booking that starts before its own grace
            # boundary, so the input offers exactly the same range: deriving the
            # boundary from the model's constant keeps the picker from refusing a
            # start the server would have accepted. Truncated to the minute, the
            # widget's precision, which leaves the picker a fraction more
            # permissive than the server rather than less; the model check stays
            # the authority. An edit carries no floor: a booking that has already
            # started is still the booker's to correct, and a floor of "now"
            # would refuse the start it already has.
            earliest = timezone.localtime(access.now_at() - BOOKING_PAST_GRACE).replace(second=0, microsecond=0)
            for name in ('start', 'end'):
                self.fields[name].widget.attrs['min'] = earliest.strftime(BOOKING_DATETIME_FORMAT)
            # ModelForm._post_clean() runs the model's clean(), and the overlap
            # and external-name rules only work once the room and author are set
            # on the instance. Assigning them here (before validation) is what
            # makes those rules run at all; a new instance never carries them in
            # the form data.
            self.instance.room = room
            self.instance.author = author
        elif not (self.instance.title or '').strip():
            # A booking made before titles existed may keep its blank title
            # while its time or description is corrected. A row that has a title
            # keeps it required, so an edit cannot silently erase it.
            self.fields['title'].required = False

    def clean_start(self):
        """Refuse moving a future booking's start into the past.

        `Booking.clean()` exempts every existing row from the past-start rule so
        the board can correct a booking whose time is over. A booker editing
        their own row does not need that exemption: the start a booking already
        has is kept, and a future booking cannot be moved behind the same grace
        boundary the create form enforces.
        """
        start = self.cleaned_data['start']
        if self.instance.pk is None or start is None:
            return start
        boundary = access.now_at() - BOOKING_PAST_GRACE
        if start < boundary and (self._initial_start is None or self._initial_start >= boundary):
            raise forms.ValidationError(_('Starttiden kan inte vara i det förflutna.'))
        return start

    def clean(self):
        """Refuse moving a booking that has already started.

        A booking is the booker's to reschedule as often as they like while it is
        still ahead. Once its start has passed, moving it would rewrite what has
        already happened, so the times are frozen and only the title and the
        description can change. The comparison is at the widget's minute
        precision, so a title-only save does not trip over the seconds the stored
        row may carry.
        """
        cleaned_data = super().clean()
        if self.instance.pk is None or self._initial_start is None or self._initial_end is None:
            return cleaned_data
        if self._initial_start > access.now_at():
            return cleaned_data
        start = cleaned_data.get('start')
        end = cleaned_data.get('end')
        if start is None or end is None:
            return cleaned_data
        same_start = start.replace(second=0, microsecond=0) == self._initial_start.replace(second=0, microsecond=0)
        same_end = end.replace(second=0, microsecond=0) == self._initial_end.replace(second=0, microsecond=0)
        if not (same_start and same_end):
            raise forms.ValidationError(
                _('Bokningen har redan börjat och kan inte flyttas. Du kan ändra titel och beskrivning i stället.')
            )
        return cleaned_data


class AnonymousBookingForm(BookingForm):
    """Booking form for a visitor without a website account.

    The email is required because it is the only channel back to the booker.
    """

    booker_name = forms.CharField(
        label=_('Namn'),
        max_length=255,
        required=True,
        error_messages={'required': _('Ange namnet på den som bokar.')},
    )
    booker_email = forms.EmailField(
        label=_('E-post'),
        required=True,
        error_messages={'required': _('Ange en e-postadress så att vi kan nå dig.')},
        # Said under the field it is about, rather than as a line under the
        # button: it explains why an address is being asked for, and a visitor
        # who is typing one is the reader.
        help_text=_('E-postadressen används bara för att skicka en bokningsbekräftelse.'),
    )

    class Meta(BookingForm.Meta):
        # mypy narrows the inherited Meta.fields to the base names, so the two
        # extra fields need an explicit ignore.
        fields = (*BookingForm.Meta.fields, 'booker_name', 'booker_email')  # type: ignore[assignment]


class CancelCodeForm(forms.Form):
    """The code from a confirmation email, which identifies one booking.

    Resolving the code to a booking is the validation: a code that matches no
    upcoming booking is a wrong code, and the page has nothing to show for it.
    """

    code = forms.CharField(
        label=_('Avbokningskod'),
        max_length=32,
        widget=forms.TextInput(attrs={'autocomplete': 'off', 'autocapitalize': 'none', 'spellcheck': 'false'}),
    )

    def __init__(self, *args, at=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.at = at
        self.booking = None

    def clean_code(self):
        code = self.cleaned_data['code'].strip()
        self.booking = access.booking_with_cancel_code(code, at=self.at)
        if self.booking is None:
            raise forms.ValidationError(_('Hittade ingen kommande bokning med den koden.'))
        return code
