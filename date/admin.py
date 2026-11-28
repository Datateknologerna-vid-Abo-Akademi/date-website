from django.contrib import admin
from django.contrib.admin.models import LogEntry
from django.utils.translation import gettext_lazy as _

from core.admin_base import ModelAdmin


@admin.register(LogEntry)
class LogEntryAdmin(ModelAdmin):
    """Read-only display of admin actions for audit logging."""

    date_hierarchy = "action_time"
    list_display = (
        "action_time",
        "user",
        "content_type",
        "object_repr",
        "action_flag",
        "change_summary",
    )
    list_filter = (
        ("user", admin.RelatedOnlyFieldListFilter),
        "content_type",
        "action_flag",
    )
    search_fields = ("object_repr",)
    ordering = ("-action_time",)
    readonly_fields = list_display
    list_select_related = ("user", "content_type")
    # The audit table is never pruned and the unfiltered total is not worth a
    # second full count on every page view.
    show_full_result_count = False

    @admin.display(description=_("Ändring"))
    def change_summary(self, obj):
        # Django stores the change record as JSON; get_change_message() returns
        # the human-readable, localized sentence an auditor can read.
        return obj.get_change_message()

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
