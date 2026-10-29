import uuid
from decimal import Decimal
from pathlib import Path

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator, MinValueValidator
from django.db import models
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from schwifty import IBAN

# One receipt may be at most this large. The form caps the total below the
# per-file limit too; the admin inline is read-only, so the form is the only
# upload path.
MAX_RECEIPT_BYTES = 10 * 1024 * 1024
RECEIPT_EXTENSIONS = ("jpg", "jpeg", "png", "gif", "webp", "pdf")


def _uuid_name(filename: str) -> str:
    """Return a random storage name, keeping only a receipt-like extension.

    The extension is not trusted: anything unrecognised is dropped rather than
    reflected into the storage path.
    """
    suffix = Path(filename).suffix.lower().lstrip(".")
    if suffix not in RECEIPT_EXTENSIONS:
        return uuid.uuid4().hex
    return f"{uuid.uuid4().hex}.{suffix}"


def receipt_upload_to(instance, filename):
    return f"expenses/receipts/{timezone.localdate().year}/{_uuid_name(filename)}"


def pdf_upload_to(instance, filename):
    year = timezone.localdate(instance.submitted_at).year if instance.submitted_at else timezone.localdate().year
    return f"expenses/pdfs/{year}/{_uuid_name(filename)}"


def validate_receipt_size(file):
    if file.size > MAX_RECEIPT_BYTES:
        raise ValidationError(
            _("Varje kvitto får vara högst %(megabytes)d MB.") % {"megabytes": MAX_RECEIPT_BYTES // (1024 * 1024)}
        )


class ExpenseClaim(models.Model):
    """A member's claim for reimbursement, with receipts and a generated PDF."""

    PAYMENT_CASH = "cash"
    PAYMENT_BANK = "bank"
    PAYMENT_CHOICES = [
        (PAYMENT_CASH, _("Kontant")),
        (PAYMENT_BANK, _("Banköverföring")),
    ]

    STATUS_PENDING = "pending"
    STATUS_APPROVED = "approved"
    STATUS_REJECTED = "rejected"
    STATUS_CHOICES = [
        (STATUS_PENDING, _("Väntar")),
        (STATUS_APPROVED, _("Godkänd")),
        (STATUS_REJECTED, _("Nekad")),
    ]

    recipient_name = models.CharField(_("Mottagare"), max_length=255)
    description = models.TextField(_("Beskrivning"))
    amount = models.DecimalField(
        _("Belopp (EUR)"),
        max_digits=8,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
        help_text=_("Beloppet i euro, till exempel 25.50."),
    )
    payment_method = models.CharField(_("Betalningsmetod"), max_length=4, choices=PAYMENT_CHOICES)
    bank_account = models.CharField(
        _("Bankkonto (IBAN)"),
        max_length=42,
        blank=True,
        help_text=_("Krävs endast för banköverföring, till exempel FI21 1234 5600 0007 85."),
    )

    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="expense_claims",
        verbose_name=_("Inskickad av"),
    )
    submitted_at = models.DateTimeField(_("Inskickad"), auto_now_add=True)

    status = models.CharField(_("Status"), max_length=8, choices=STATUS_CHOICES, default=STATUS_PENDING)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="reviewed_expense_claims",
        verbose_name=_("Behandlad av"),
    )
    reviewed_at = models.DateField(_("Behandlad"), null=True, blank=True)
    treasurer_signature_date = models.DateField(_("Kassörens signeringsdatum"), null=True, blank=True)

    pdf = models.FileField(_("PDF"), upload_to=pdf_upload_to, blank=True)
    pdf_generated_at = models.DateTimeField(_("PDF genererad"), null=True, blank=True)

    class Meta:
        ordering = ["-submitted_at"]
        verbose_name = _("kostnadsersättning")
        verbose_name_plural = _("kostnadsersättningar")
        constraints = [
            models.CheckConstraint(
                condition=models.Q(amount__gt=0),
                name="expenses_expenseclaim_amount_positive",
            ),
            models.CheckConstraint(
                condition=~models.Q(payment_method="bank") | models.Q(bank_account__gt=""),
                name="expenses_expenseclaim_bank_account_required",
            ),
        ]

    def __str__(self):
        return f"{self.recipient_name}, {self.amount} EUR"

    def get_absolute_url(self):
        return reverse("expenses:detail", args=[self.pk])

    def clean(self):
        super().clean()
        if self.payment_method != self.PAYMENT_BANK:
            self.bank_account = ""
            return
        account = (self.bank_account or "").strip()
        if not account:
            raise ValidationError({"bank_account": _("Bankkonto (IBAN) krävs för banköverföring.")})
        try:
            # Stored formatted so the same value reads well on the page and in
            # the PDF. Validating here rather than only in the site form is what
            # makes the admin change form check the IBAN too.
            self.bank_account = IBAN(account).formatted
        except ValueError as error:
            raise ValidationError({"bank_account": _("Ogiltigt IBAN-nummer.")}) from error

    @property
    def is_reviewed(self):
        return self.status != self.STATUS_PENDING

    @property
    def pdf_filename(self):
        return f"kostnadsersattning-{self.pk}.pdf"


class ExpenseReceipt(models.Model):
    claim = models.ForeignKey(
        ExpenseClaim,
        on_delete=models.CASCADE,
        related_name="receipts",
        verbose_name=_("Kostnadsersättning"),
    )
    file = models.FileField(
        _("Fil"),
        upload_to=receipt_upload_to,
        validators=[
            FileExtensionValidator(
                RECEIPT_EXTENSIONS,
                message=_("Endast bilder (JPEG, PNG, GIF, WebP) och PDF-filer är tillåtna."),
            ),
            validate_receipt_size,
        ],
    )
    uploaded_at = models.DateTimeField(_("Uppladdad"), auto_now_add=True)

    class Meta:
        ordering = ["uploaded_at", "pk"]
        verbose_name = _("kvitto")
        verbose_name_plural = _("kvitton")

    def __str__(self):
        return _("Kvitto #%(pk)s") % {"pk": self.pk}

    @property
    def is_pdf(self):
        return Path(self.file.name).suffix.lower() == ".pdf"
