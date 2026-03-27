import uuid
from datetime import date

from django.db import models
from django.db.models import CASCADE, SET_NULL


def _uuid_name(filename):
    ext = filename.rsplit('.', 1)[-1] if '.' in filename else ''
    return f'{uuid.uuid4().hex}.{ext}' if ext else uuid.uuid4().hex


def receipt_upload_to(instance, filename):
    year = date.today().year
    return f'expenses/receipts/{year}/{_uuid_name(filename)}'


def pdf_upload_to(instance, filename):
    year = instance.submitted_at.year if instance.submitted_at else date.today().year
    return f'expenses/pdfs/{year}/{_uuid_name(filename)}'


class ExpenseClaim(models.Model):
    PAYMENT_CASH = 'cash'
    PAYMENT_BANK = 'bank'
    PAYMENT_CHOICES = [('cash', 'Kontant'), ('bank', 'Banköverföring')]

    STATUS_PENDING = 'pending'
    STATUS_APPROVED = 'approved'
    STATUS_REJECTED = 'rejected'
    STATUS_CHOICES = [('pending', 'Pending'), ('approved', 'Approved'), ('rejected', 'Rejected')]

    recipient_name = models.CharField(max_length=255)
    description = models.TextField()
    amount = models.DecimalField(max_digits=8, decimal_places=2)
    payment_method = models.CharField(max_length=4, choices=PAYMENT_CHOICES)
    bank_account = models.CharField(max_length=100, blank=True)

    submitted_by = models.ForeignKey('members.Member', on_delete=CASCADE, related_name='expense_claims')
    submitted_at = models.DateTimeField(auto_now_add=True)

    status = models.CharField(max_length=8, choices=STATUS_CHOICES, default='pending')
    approved_by = models.ForeignKey(
        'members.Member', null=True, blank=True, on_delete=SET_NULL, related_name='approved_expense_claims'
    )
    approved_at = models.DateField(null=True, blank=True)
    treasurer_signature_date = models.DateField(null=True, blank=True)

    pdf = models.FileField(upload_to=pdf_upload_to, blank=True)
    pdf_generated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-submitted_at']

    def __str__(self):
        return f'{self.recipient_name} – {self.amount} EUR ({self.submitted_at.date() if self.submitted_at else ""})'


class ExpenseReceipt(models.Model):
    claim = models.ForeignKey(ExpenseClaim, on_delete=CASCADE, related_name='receipts')
    file = models.FileField(upload_to=receipt_upload_to)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'Receipt for claim #{self.claim_id}'
