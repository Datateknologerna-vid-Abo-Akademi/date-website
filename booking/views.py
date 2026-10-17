import logging

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import transaction
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django.views.generic import ListView

from core.utils import validate_captcha

from . import access, emails
from .forms import AnonymousBookingForm, BookingForm, CancelCodeForm
from .models import Booking, BookingSettings, Closure, Room

logger = logging.getLogger('date')

UPCOMING_BOOKING_LIMIT = 50


def _code_instructions():
    """The board's own wording for how a visitor is given the code, if any.

    Read directly rather than through ``get_solo()``: a public page has no
    reason to create the settings row, and a row that is not there yet simply
    means no text of the board's own. The channel itself is deliberately not
    decided anywhere in this app, because the board is the one that hands the
    code out, and it does that however it likes.
    """
    settings_row = BookingSettings.objects.filter(pk=1).only('code_instructions').first()
    return settings_row.code_instructions if settings_row else ''


def _upcoming_closures(room):
    """The room's closures that are still to come, soonest first.

    Shown on the room page so a visitor looking at the calendar sees why the room
    is unavailable, rather than filling in the form and being refused.
    """
    return Closure.objects.filter(room=room, end__gte=access.now_at()).order_by('start', 'pk')[:UPCOMING_BOOKING_LIMIT]


def _upcoming_bookings(rooms=None):
    """Future bookings of active rooms, furthest away last.

    Callers render times and room names only: everything here is public, so the
    booking description, the booker name and the booker email stay out of the
    templates.
    """
    upcoming = Booking.objects.filter(end__gte=access.now_at())
    if rooms is not None:
        upcoming = upcoming.filter(room__in=rooms)
    return upcoming.select_related('room').order_by('start')


class RoomListView(ListView):
    template_name = 'booking/index.html'
    context_object_name = 'room_list'

    def get_queryset(self):
        # No caching on purpose: an admin edit has to show up at once.
        return Room.objects.all()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['bookings'] = _upcoming_bookings()[:UPCOMING_BOOKING_LIMIT]
        # The link to a member's own bookings is offered only when there is
        # something behind it, so it never leads to an empty page.
        context['has_my_bookings'] = (
            self.request.user.is_authenticated
            and Booking.objects.filter(author=self.request.user, end__gte=access.now_at()).exists()
        )
        return context


def room_detail(request, pk):
    room = get_object_or_404(Room, pk=pk)
    at = access.now_at()

    if not request.user.is_authenticated and (
        access.is_code_submission(request) or not access.session_has_access(request, room)
    ):
        return access.booking_code_gate(
            request,
            room=room,
            template_name='booking/room_detail.html',
            context={
                'room': room,
                'bookings': _upcoming_bookings(rooms=[room])[:UPCOMING_BOOKING_LIMIT],
                'closures': _upcoming_closures(room),
                'code_instructions': _code_instructions(),
            },
            next_url=reverse('booking:room_detail', args=[room.pk]),
            at=at,
        )

    form_class = BookingForm if request.user.is_authenticated else AnonymousBookingForm

    if request.method == 'POST':
        # Lock the room row first so two simultaneous submissions cannot both
        # pass the overlap check. SQLite ignores the lock, so the tests cannot
        # prove this part; PostgreSQL is what production runs.
        with transaction.atomic():
            locked_room = Room.objects.select_for_update().get(pk=room.pk)
            if request.user.is_authenticated:
                form = form_class(request.POST, room=locked_room, author=request.user)
                allowed = form.is_valid()
            else:
                form = form_class(request.POST, room=locked_room)
                allowed = form.is_valid()
                if allowed and not validate_captcha(access.captcha_response(request)):
                    # Say so, rather than re-rendering a valid-looking form and
                    # leaving the visitor to retry it forever.
                    logger.warning('Booking captcha rejected for room %s', room.pk)
                    form.add_error(None, _('Kunde inte verifiera att du inte är en robot. Försök igen.'))
                    allowed = False
            if allowed:
                booking = form.save()
                emails.notify_booker(booking, request=request)
                # The page says so as well, and keeps saying so whether or not
                # there was an address to mail: the mail complements this, it
                # does not replace it.
                messages.success(request, _('Tack! Din bokning är registrerad.'))
                return redirect('booking:room_detail', pk=room.pk)
    else:
        form = form_class(room=room, author=request.user if request.user.is_authenticated else None)

    return render(
        request,
        'booking/room_detail.html',
        {
            'room': room,
            'bookings': _upcoming_bookings(rooms=[room])[:UPCOMING_BOOKING_LIMIT],
            'closures': _upcoming_closures(room),
            'form': form,
        },
    )


def _member_upcoming(user):
    """The member's own bookings that have not finished yet."""
    return Booking.objects.filter(author=user, end__gte=access.now_at()).select_related('room').order_by('start', 'pk')


class MyBookingsView(LoginRequiredMixin, ListView):
    """A member's own upcoming bookings, and cancelling one of them.

    The page is only linked from the room list when there is something on it, so
    a member with no bookings never sees an entry that leads to an empty page.
    Cancelling checks the account rather than a code: the booking has to belong
    to the signed-in member, so a code to type would protect nothing.
    """

    template_name = 'booking/my_bookings.html'
    context_object_name = 'bookings'

    def get_queryset(self):
        return _member_upcoming(self.request.user)

    def post(self, request, *args, **kwargs):
        pk = request.POST.get('booking', '')
        booking = None
        # Bounded before the query: a long enough run of digits overflows the
        # conversion Django does for the primary key, which would be a server
        # error rather than the not-found a nonsense id deserves.
        if pk.isdecimal() and len(pk) <= 18:
            booking = _member_upcoming(request.user).filter(pk=pk).first()
        if booking is None:
            # Either the id is nonsense, or it is somebody else's booking, or it
            # has already finished and dropped out of the queryset. All three
            # look the same from here on purpose.
            raise Http404
        booking.delete()
        messages.success(request, _('Bokningen är borttagen.'))
        return redirect('booking:my_bookings')


def cancel_booking(request):
    """Cancel a booking made without an account, using the code from the email.

    Two steps on purpose. A link that cancels on a GET would be followed by the
    link scanners that mailbox providers run over incoming mail, and a booking
    could disappear before its owner ever read the message. The code identifies
    the booking, the page shows which one it is, and only the confirmation
    button on that page deletes it.
    """
    at = access.now_at()
    form = CancelCodeForm(at=at)
    booking = None

    if request.method == 'POST':
        form = CancelCodeForm(request.POST, at=at)
        if form.is_valid():
            booking = form.booking
            if 'confirm' in request.POST:
                booking.delete()
                messages.success(request, _('Bokningen är borttagen.'))
                return redirect('booking:index')
    elif request.GET.get('code'):
        # Bound so the code is validated and any complaint is a field error on a
        # rendered page. A visitor who follows the link from their email with a
        # code that no longer works deserves the form and the message, not a
        # bare error page.
        form = CancelCodeForm({'code': request.GET['code']}, at=at)
        if form.is_valid():
            booking = form.booking

    return render(request, 'booking/cancel_booking.html', {'form': form, 'booking': booking})
