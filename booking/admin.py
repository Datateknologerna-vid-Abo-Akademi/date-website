from django.contrib import admin
from django.db.models import Count
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
    list_display = ('room', 'time_range', 'booker_display', 'is_external')
    list_filter = ('room', 'start')
    date_hierarchy = 'start'
    search_fields = ('booker_name', 'booker_email', 'description')
    list_select_related = ('room', 'author')
    autocomplete_fields = ('room', 'author')
    readonly_fields = ('booker_display', 'is_external')

    @admin.display(description=_('Tid'))
    def time_range(self, obj):
        # localtime, not strftime on the stored value: USE_TZ is on and the
        # column has to read in the association's timezone, not UTC.
        start = timezone.localtime(obj.start)
        end = timezone.localtime(obj.end)
        return f'{start:%Y-%m-%d %H:%M} - {end:%H:%M}'

    @admin.display(boolean=True, description=_('Extern bokning'))
    def is_external(self, obj):
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
