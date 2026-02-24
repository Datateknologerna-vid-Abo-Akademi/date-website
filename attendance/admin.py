from django.contrib import admin

from . import models

class AttendanceChangesInline(admin.TabularInline):
    model = models.AttendanceChange
    classes = ["collapse"]


class AttendanceEventAdmin(admin.ModelAdmin):
    inlines = [AttendanceChangesInline]


class AttendanceChangeAdmin(admin.ModelAdmin):
    pass


admin.site.register(models.AttendanceEvent, AttendanceEventAdmin)
admin.site.register(models.AttendanceChange, AttendanceChangeAdmin)
