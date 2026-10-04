from django.contrib import admin

from . import models


class AttendanceChangesInline(admin.TabularInline):
    model = models.AttendanceChange
    classes = ["collapse"]


class AttendanceEventAdmin(admin.ModelAdmin):
    # The workflow is "find the event, open its overview page", so the list is
    # ordered newest first and carries the times and the guest switch. Without
    # this the changelist shows titles only and cannot be searched.
    list_display = ("title", "start_datetime", "end_datetime", "allow_non_members")
    list_filter = ("allow_non_members", "start_datetime")
    search_fields = ("title", "description", "slug")
    date_hierarchy = "start_datetime"
    ordering = ("-start_datetime",)
    inlines = [AttendanceChangesInline]


class AttendanceChangeAdmin(admin.ModelAdmin):
    list_display = ("timestamp", "event", "user", "non_member", "type")
    list_filter = ("type", "event")
    search_fields = (
        "event__title",
        "user__username",
        "user__first_name",
        "user__last_name",
        "non_member__name",
    )
    date_hierarchy = "timestamp"
    ordering = ("-timestamp",)


admin.site.register(models.AttendanceEvent, AttendanceEventAdmin)
admin.site.register(models.AttendanceChange, AttendanceChangeAdmin)
