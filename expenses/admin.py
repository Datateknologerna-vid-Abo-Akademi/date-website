from django.contrib import admin

from .models import ExpenseClaim, ExpenseReceipt


class ExpenseReceiptInline(admin.TabularInline):
    model = ExpenseReceipt
    extra = 0
    readonly_fields = ['file', 'uploaded_at']


@admin.register(ExpenseClaim)
class ExpenseClaimAdmin(admin.ModelAdmin):
    list_display = ['recipient_name', 'amount', 'payment_method', 'status', 'submitted_by', 'submitted_at', 'pdf_ready']
    list_filter = ['status', 'payment_method']
    readonly_fields = ['submitted_by', 'submitted_at', 'pdf', 'pdf_generated_at']
    fields = [
        'recipient_name', 'description', 'amount', 'payment_method', 'bank_account',
        'submitted_by', 'submitted_at',
        'status', 'approved_by', 'approved_at', 'treasurer_signature_date',
        'pdf', 'pdf_generated_at',
    ]
    inlines = [ExpenseReceiptInline]

    def pdf_ready(self, obj):
        return bool(obj.pdf)
    pdf_ready.boolean = True
    pdf_ready.short_description = 'PDF ready'
