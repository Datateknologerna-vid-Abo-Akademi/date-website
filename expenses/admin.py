from django.contrib import admin
from django.urls import reverse
from django.utils import timezone
from django.utils.html import format_html

from .models import ExpenseClaim, ExpenseReceipt


class ExpenseReceiptInline(admin.TabularInline):
    model = ExpenseReceipt
    extra = 0
    readonly_fields = ['file', 'uploaded_at']


@admin.register(ExpenseClaim)
class ExpenseClaimAdmin(admin.ModelAdmin):
    list_display = ['recipient_name', 'amount', 'payment_method', 'status', 'submitted_by', 'submitted_at', 'pdf_ready']
    list_filter = ['status', 'payment_method']
    readonly_fields = ['submitted_by', 'submitted_at', 'pdf_download_link', 'pdf_generated_at']
    fields = [
        'recipient_name', 'description', 'amount', 'payment_method', 'bank_account',
        'submitted_by', 'submitted_at',
        'status', 'approved_by', 'approved_at', 'treasurer_signature_date',
        'pdf_download_link', 'pdf_generated_at',
    ]
    inlines = [ExpenseReceiptInline]
    actions = ['regenerate_pdf', 'mark_approved', 'mark_rejected']

    def pdf_ready(self, obj):
        return bool(obj.pdf)
    pdf_ready.boolean = True
    pdf_ready.short_description = 'PDF ready'

    def pdf_download_link(self, obj):
        if not obj.pdf:
            return '—'
        url = reverse('expenses:pdf', args=[obj.pk])
        return format_html('<a href="{}">Ladda ned PDF</a>', url)
    pdf_download_link.short_description = 'PDF'

    @admin.action(description='Regenerera PDF')
    def regenerate_pdf(self, request, queryset):
        from .tasks import generate_expense_pdf
        for claim in queryset:
            generate_expense_pdf.delay(claim.pk)
        self.message_user(request, f'PDF-generering startad för {queryset.count()} utlägg.')

    @admin.action(description='Markera som godkänd')
    def mark_approved(self, request, queryset):
        queryset.update(
            status=ExpenseClaim.STATUS_APPROVED,
            approved_by_id=request.user.pk,
            approved_at=timezone.now().date(),
        )
        self.message_user(request, f'{queryset.count()} utlägg markerade som godkända.')

    @admin.action(description='Markera som nekad')
    def mark_rejected(self, request, queryset):
        queryset.update(
            status=ExpenseClaim.STATUS_REJECTED,
            approved_by_id=request.user.pk,
            approved_at=timezone.now().date(),
        )
        self.message_user(request, f'{queryset.count()} utlägg markerade som nekade.')
