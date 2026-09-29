import logging

from django.contrib import messages
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.views.generic import ListView

from core.utils import validate_captcha

from . import access, emails
from .forms import AnonymousBookingForm, BookingForm
from .models import Booking, Room

logger = logging.getLogger('date')

UPCOMING_BOOKING_LIMIT = 50


def _upcoming_bookings(rooms=None):
    """Future bookings of active rooms, furthest away last.

    Callers render times and room names only: everything here is public, so the
    booking description, the booker name and the booker email stay out of the
    templates.
    """
    upcoming = Booking.objects.filter(room__is_active=True, end__gte=timezone.now())
    if rooms is not None:
        upcoming = upcoming.filter(room__in=rooms)
    return upcoming.select_related('room').order_by('start')


class RoomListView(ListView):
    template_name = 'booking/index.html'
    context_object_name = 'room_list'

    def get_queryset(self):
        # No caching on purpose: an admin edit has to show up at once.
        return Room.objects.filter(is_active=True)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['bookings'] = _upcoming_bookings()[:UPCOMING_BOOKING_LIMIT]
        return context


def room_detail(request, pk):
    room = get_object_or_404(Room, pk=pk, is_active=True)
    at = access.now_at()

    if not request.user.is_authenticated and not access.session_has_access(request, at):
        return access.booking_code_gate(
            request,
            template_name='booking/room_detail.html',
            context={
                'room': room,
                'bookings': _upcoming_bookings(rooms=[room])[:UPCOMING_BOOKING_LIMIT],
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
                if allowed and not validate_captcha(request.POST.get('cf-turnstile-response')):
                    # Say so, rather than re-rendering a valid-looking form and
                    # leaving the visitor to retry it forever.
                    logger.warning('Booking captcha rejected for room %s', room.pk)
                    form.add_error(None, _('Kunde inte verifiera att du inte är en robot. Försök igen.'))
                    allowed = False
            if allowed:
                booking = form.save()
                emails.notify_external_booker(booking)
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
            'form': form,
        },
    )
