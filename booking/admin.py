from django.contrib import admin
from django.db.models import Count, Q
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from core.admin_base import ModelAdmin, TabularInline

from . import access
from .models import Booking, BookingSettings, Room


class BookingInline(TabularInline):
    model = Booking
    fk_name = 'room'
    extra = 0
    fields = ('start', 'end', 'author', 'booker_name', 'description')
    autocomplete_fields = ('author',)
    show_change_link = True

    def get_queryset(self, request):
        # A room collects bookings for years, and Django does not paginate
        # inlines, so an unfiltered inline would grow without bound and open on
        # the oldest rows. Show the bookings the board can still act on, soonest
        # first; the Booking changelist holds the whole history, with the filters
        # and the date drill-down that reach it.
        queryset = super().get_queryset(request).order_by('start', 'pk')
        visible = Q(end__gte=timezone.now())
        submitted = self._submitted_pks(request)
        if submitted:
            # A row the board was shown stays in the formset even if its end
            # passed while the page was open. Without this Django resolves the
            # submitted id to an unsaved instance and drops the row's checked
            # Delete, while the save still reports success.
            visible |= Q(pk__in=submitted)
        return queryset.filter(visible)

    @staticmethod
    def _submitted_pks(request):
        """The booking ids the submitted inline formset names, if any.

        Keyed on the prefix Django gives this formset, which it derives from the
        FK accessor name, so a row belonging to another inline on the same page
        is never pulled in.
        """
        if request.method != 'POST':
            return set()
        accessor = Booking._meta.get_field('room').remote_field.get_accessor_name(model=Booking)
        prefix = f'{accessor.replace("+", "")}-'
        pks = set()
        for key, values in request.POST.lists():
            # Exactly "<prefix><index>-id": any other key, including one that
            # merely starts with the prefix, belongs to something else.
            if not key.startswith(prefix) or not key.endswith('-id'):
                continue
            if not key[len(prefix) : -len('-id')].isdecimal():
                continue
            # isdecimal(), not isdigit(): isdigit() also accepts characters such
            # as a superscript two, which int() refuses. The length bound keeps a
            # stray long string out of int(), which has its own limit.
            pks.update(int(value) for value in values if value.isdecimal() and len(value) <= 18)
        return pks


class BookingOriginFilter(admin.SimpleListFilter):
    """Split bookings made through a member account from the public form.

    ``author`` is nulled when a member deletes the account, so the account
    alone does not answer "did this come from the website form?". The public
    form requires an email address and a member booking never records one, so
    the two together separate the cases.
    """

    title = _('Bokningens ursprung')
    parameter_name = 'origin'

    def lookups(self, request, model_admin):
        return (
            ('account', _('Bokning av en medlem')),
            ('external', _('Bokning utan konto, via webbformuläret')),
            ('no_account', _('Bokning utan konto')),
        )

    def queryset(self, request, queryset):
        if self.value() == 'account':
            return queryset.filter(author__isnull=False)
        if self.value() == 'external':
            return queryset.filter(author__isnull=True).exclude(booker_email='')
        if self.value() == 'no_account':
            return queryset.filter(author__isnull=True)
        return queryset


@admin.register(Room)
class RoomAdmin(ModelAdmin):
    list_display = ('name', 'is_active', 'booking_count')
    list_filter = ('is_active',)
    search_fields = ('name',)
    inlines = [BookingInline]

    def get_queryset(self, request):
        # Annotated so the changelist does not run one COUNT per room.
        return super().get_queryset(request).annotate(bookings_total=Count('bookings'))

    @admin.display(description=_('Bokningar'), ordering='bookings_total')
    def booking_count(self, obj):
        return obj.bookings_total


@admin.register(Booking)
class BookingAdmin(ModelAdmin):
    list_display = ('room', 'time_range', 'booker_display', 'no_account')
    list_filter = (BookingOriginFilter, 'room', 'start')
    date_hierarchy = 'start'
    search_fields = ('booker_name', 'booker_email', 'description')
    list_select_related = ('room', 'author')
    autocomplete_fields = ('room', 'author')
    readonly_fields = ('booker_display', 'no_account')
    # Newest first, so the changelist does not open on the oldest booking ever
    # made. This matches the descending ordering the other time-ordered admins
    # in this project use.
    ordering = ('-start',)

    @admin.display(description=_('Tid'))
    def time_range(self, obj):
        # localtime, not strftime on the stored value: USE_TZ is on and the
        # column has to read in the association's timezone, not UTC.
        start = timezone.localtime(obj.start)
        end = timezone.localtime(obj.end)
        return f'{start:%Y-%m-%d %H:%M} - {end:%H:%M}'

    @admin.display(boolean=True, description=_('Utan konto'))
    def no_account(self, obj):
        # "Utan konto", not "extern": a booking made by a member who later
        # deleted the account has no account either, and the Bokare column
        # still shows who booked it.
        return obj.is_external

    @admin.display(description=_('Bokare'))
    def booker_display(self, obj):
        return obj.booker_display


@admin.register(BookingSettings)
class BookingSettingsAdmin(ModelAdmin):
    list_display = ('__str__', 'rotation_period', 'current_code', 'next_rotation')
    readonly_fields = ('current_code', 'next_rotation')
    fieldsets = (
        (
            None,
            {
                'fields': ('rotation_period',),
                'description': _('Bokningskoden genereras automatiskt och kan inte skrivas in här. Den visas nedan.'),
            },
        ),
        (
            _('Aktuell bokningskod'),
            {
                'fields': ('current_code', 'next_rotation'),
            },
        ),
    )

    def has_add_permission(self, request):
        return not BookingSettings.objects.exists() and super().has_add_permission(request)

    def has_delete_permission(self, request, obj=None):
        return False

    @admin.display(description=_('Aktuell bokningskod'))
    def current_code(self, obj):
        return access.current_code(access_settings=self._settings_for(obj))

    @admin.display(description=_('Koden byts ut'))
    def next_rotation(self, obj):
        return access.next_rotation(access_settings=self._settings_for(obj))

    @staticmethod
    def _settings_for(obj):
        # Never get_solo() while rendering: the add page has no stored row yet,
        # and creating one here would make has_add_permission refuse the very
        # POST the admin just filled in. An unsaved instance carries the model
        # default period, and only rotation_period is ever read.
        return obj if obj and obj.pk else BookingSettings()
