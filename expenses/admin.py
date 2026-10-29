import logging

from django.contrib import admin, messages
from django.urls import reverse
from django.utils import timezone
from django.utils.html import format_html
from django.utils.text import format_lazy
from django.utils.translation import gettext_lazy as _

from core.admin_base import ModelAdmin, TabularInline

from .models import ExpenseClaim, ExpenseReceipt
from .tasks import generate_expense_pdf

logger = logging.getLogger("date")


class ExpenseReceiptInline(TabularInline):
    model = ExpenseReceipt
    extra = 0
    fields = ("receipt_link", "uploaded_at")
    readonly_fields = ("receipt_link", "uploaded_at")

    def has_add_permission(self, request, obj=None):
        # Receipts arrive with the member's submission; an admin-added row would
        # have no file, because every field here is read-only.
        return False

    def has_delete_permission(self, request, obj=None):
        # The PDF was built with these receipts. Removing one would leave the
        # signed record disagreeing with the database, and the inline cannot
        # regenerate the PDF.
        return False

    @admin.display(description=_("Kvitto"))
    def receipt_link(self, obj):
        if not obj.pk:
            return ""
        return format_html(
            '<a href="{}" target="_blank" rel="noopener">{}</a>',
            reverse("expenses:receipt", args=[obj.pk]),
            _("Öppna kvitto"),
        )


@admin.register(ExpenseClaim)
class ExpenseClaimAdmin(ModelAdmin):
    list_display = (
        "recipient_name",
        "amount",
        "payment_method",
        "status",
        "submitted_by",
        "submitted_at",
        "pdf_ready",
    )
    list_filter = ("status", "payment_method")
    list_select_related = ("submitted_by", "reviewed_by")
    search_fields = (
        "recipient_name",
        "description",
        "submitted_by__first_name",
        "submitted_by__last_name",
        "submitted_by__username",
    )
    date_hierarchy = "submitted_at"
    readonly_fields = ("submitted_by", "submitted_at", "pdf_download_link", "pdf_generated_at")
    fields = (
        "recipient_name",
        "description",
        "amount",
        "payment_method",
        "bank_account",
        "submitted_by",
        "submitted_at",
        "status",
        "reviewed_by",
        "reviewed_at",
        "treasurer_signature_date",
        "pdf_download_link",
        "pdf_generated_at",
    )
    inlines = (ExpenseReceiptInline,)
    actions = ("regenerate_pdf", "mark_approved", "mark_rejected")

    def has_add_permission(self, request):
        # A claim is submitted by a member from the site; the add form could not
        # set the read-only submitted_by, so an admin-created row would fail.
        return False

    @admin.display(boolean=True, description=_("PDF"))
    def pdf_ready(self, obj):
        return bool(obj.pdf)

    @admin.display(description=_("PDF"))
    def pdf_download_link(self, obj):
        if not obj.pk or not obj.pdf:
            return _("Inte genererad")
        return format_html(
            '<a href="{}">{}</a>',
            reverse("expenses:pdf", args=[obj.pk]),
            _("Ladda ned PDF"),
        )

    @admin.action(description=_("Generera PDF på nytt"), permissions=["change"])
    def regenerate_pdf(self, request, queryset):
        started = 0
        failed = 0
        for claim in queryset:
            try:
                generate_expense_pdf.delay(claim.pk)
            except Exception:
                logger.exception("Could not queue PDF regeneration for expense claim %s", claim.pk)
                failed += 1
            else:
                started += 1
        self.message_user(request, format_lazy(_("PDF-generering startad för {count} utlägg."), count=started))
        if failed:
            self.message_user(
                request,
                format_lazy(_("PDF-generering kunde inte startas för {count} utlägg."), count=failed),
                level=messages.WARNING,
            )

    @admin.action(description=_("Godkänn valda utlägg"), permissions=["change"])
    def mark_approved(self, request, queryset):
        self._mark_reviewed(request, queryset, ExpenseClaim.STATUS_APPROVED, _("godkända"))

    @admin.action(description=_("Neka valda utlägg"), permissions=["change"])
    def mark_rejected(self, request, queryset):
        self._mark_reviewed(request, queryset, ExpenseClaim.STATUS_REJECTED, _("nekade"))

    def _mark_reviewed(self, request, queryset, status: str, label) -> None:
        """Decide the pending claims only; a decision is not overwritten silently."""
        updated = queryset.filter(status=ExpenseClaim.STATUS_PENDING).update(
            status=status,
            reviewed_by_id=request.user.pk,
            reviewed_at=timezone.localdate(),
        )
        skipped = queryset.count() - updated
        self.message_user(request, format_lazy(_("{count} utlägg markerade som {label}."), count=updated, label=label))
        if skipped:
            self.message_user(
                request,
                format_lazy(_("{count} utlägg hoppades över eftersom de redan hade behandlats."), count=skipped),
                level=messages.WARNING,
            )
