from django import forms
from django.conf import settings
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from . import access
from .models import BOOKING_PAST_GRACE, Booking

BOOKING_DATETIME_FORMAT = '%Y-%m-%dT%H:%M'


def _local_datetime_widget():
    """A datetime-local input that keeps the browser value after a reload."""
    return forms.DateTimeInput(attrs={'type': 'datetime-local'}, format=BOOKING_DATETIME_FORMAT)


def local_datetime_field(label):
    """A DateTimeField wired to the datetime-local widget it renders.

    ``input_formats`` belongs to the field rather than to the widget, so both
    halves are built here: the browser value has to be accepted and a value
    that failed validation still has to come back in the input's own format.
    """
    widget = _local_datetime_widget()
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

    def __init__(self, *args, at=None, access_settings=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.at = at
        self.access_settings = access_settings

    def clean_code(self):
        code = self.cleaned_data['code']
        if not access.check_code(code, at=self.at, access_settings=self.access_settings):
            raise forms.ValidationError(_('Fel kod.'))
        return code


class BookingForm(forms.ModelForm):
    start = local_datetime_field(_('Starttid'))
    end = local_datetime_field(_('Sluttid'))
    description = forms.CharField(
        label=_('Beskrivning'),
        max_length=400,
        required=False,
        widget=forms.Textarea(attrs={'rows': 3}),
        help_text=_('Berätta kort vad utrymmet ska användas till. Endast styrelsen ser detta.'),
    )

    class Meta:
        model = Booking
        fields = ('start', 'end', 'description')

    def __init__(self, *args, room=None, author=None, **kwargs):
        super().__init__(*args, **kwargs)
        if room is not None:
            self.room = room
        if author is not None:
            self.author = author
        # The model refuses a new booking that starts before its own grace
        # boundary, so the input offers exactly the same range: deriving the
        # boundary from the model's constant keeps the picker from refusing a
        # start the server would have accepted. Truncated to the minute, the
        # widget's precision, which leaves the picker a fraction more permissive
        # than the server rather than less; the model check stays the authority.
        earliest = timezone.localtime(access.now_at() - BOOKING_PAST_GRACE).replace(second=0, microsecond=0)
        for name in ('start', 'end'):
            self.fields[name].widget.attrs['min'] = earliest.strftime(BOOKING_DATETIME_FORMAT)
        # ModelForm._post_clean() runs the model's clean(), and the overlap and
        # external-name rules only work once the room and author are set on the
        # instance. Assigning them here (before validation) is what makes those
        # rules run at all; a new instance never carries them in the form data.
        if self.instance.pk is None:
            self.instance.room = room
            self.instance.author = author


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
    )

    class Meta(BookingForm.Meta):
        # mypy narrows the inherited Meta.fields to the three base names, so the
        # two extra fields need an explicit ignore.
        fields = (*BookingForm.Meta.fields, 'booker_name', 'booker_email')  # type: ignore[assignment]
