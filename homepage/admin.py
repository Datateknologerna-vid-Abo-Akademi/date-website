from django.contrib import admin
from django.contrib.admin.models import LogEntry


@admin.register(LogEntry)
class LogEntryAdmin(admin.ModelAdmin):
    """Read-only display of admin actions for audit logging."""

    date_hierarchy = "action_time"
    list_display = (
        "action_time",
        "user",
        "content_type",
        "object_repr",
        "action_flag",
        "change_message",
    )
    list_filter = ("user", "content_type", "action_flag")
    search_fields = ("object_repr", "change_message")
    ordering = ("-action_time",)
    readonly_fields = list_display

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
