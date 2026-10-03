from django.contrib import admin, messages
from django.db.models import Count, Q
from django.utils import formats, timezone
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
    list_display = ('name', 'is_active', 'current_code', 'last_rotated', 'booking_count')
    list_filter = ('is_active',)
    search_fields = ('name',)
    inlines = [BookingInline]
    actions = ('rotate_code',)
    readonly_fields = ('current_code', 'last_rotated')

    def get_queryset(self, request):
        # Annotated so the changelist does not run one COUNT per room.
        return super().get_queryset(request).annotate(bookings_total=Count('bookings'))

    def save_model(self, request, obj, form, change):
        # Only the fields the board can edit are written, which is name,
        # description and is_active. A plain save() would also put back the
        # generation and the rotation moment from whatever this request read,
        # undoing a rotation that landed in between and reviving the unlocks it
        # had just ended. On an insert update_fields is ignored and every field
        # is written, which is what the two defaults need.
        editable = [f.name for f in obj._meta.concrete_fields if f.editable and not f.primary_key]
        obj.save(update_fields=editable)

    @admin.display(description=_('Bokningar'), ordering='bookings_total')
    def booking_count(self, obj):
        return obj.bookings_total

    @admin.display(description=_('Aktuell bokningskod'))
    def current_code(self, obj):
        if not obj or not obj.pk:
            return '-'
        return access.current_code(obj)

    @admin.display(description=_('Senast bytt'))
    def last_rotated(self, obj):
        if not obj or not obj.pk or not obj.rotated_at:
            return _('Aldrig')
        # Formatted rather than handed to the template as a datetime: Django
        # would render the raw repr, offset and all.
        return formats.date_format(timezone.localtime(obj.rotated_at), 'DATETIME_FORMAT')

    @admin.action(description=_('Byt bokningskoden nu'), permissions=['change'])
    def rotate_code(self, request, queryset):
        """Hand the board a new code per room, ending the unlocks each granted."""
        for room in queryset:
            generation = room.rotate_code()
            self.message_user(
                request,
                _('Ny bokningskod för %(room)s: %(code)s. Den förra koden fungerar i 15 minuter till.')
                % {'room': room.name, 'code': access.code_for_generation(room, generation)},
                messages.SUCCESS,
            )


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
    """The association-wide note about how a visitor gets a code.

    The codes themselves live on each room, so this page has no code to show and
    nothing to rotate.
    """

    list_display = ('__str__',)
    fieldsets = (
        (
            None,
            {
                'fields': ('code_instructions',),
                'description': _(
                    'Varje utrymme har sin egen bokningskod, som visas och byts på utrymmets sida under '
                    'Bokningar › Utrymmen. Här står bara texten som besökare utan konto får läsa.'
                ),
            },
        ),
    )

    def has_add_permission(self, request):
        return not BookingSettings.objects.exists() and super().has_add_permission(request)

    def has_delete_permission(self, request, obj=None):
        return False
