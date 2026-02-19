from django.contrib import admin
from booking.models import Booking, Room


# Register your models here.
class BookingInline(admin.TabularInline):
    model = Booking
    can_delete = True
    extra = 1

class RoomAdmin(admin.ModelAdmin):
    model = Room
    save_on_top = True
    inlines = [
        BookingInline
    ]
    list_display = ['name']


admin.site.register(Room, RoomAdmin)