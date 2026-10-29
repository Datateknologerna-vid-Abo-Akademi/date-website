from pathlib import Path

from django import forms
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from PIL import Image
from pypdf import PdfReader
from pypdf.errors import PyPdfError

from .models import MAX_RECEIPT_BYTES, RECEIPT_EXTENSIONS, ExpenseClaim

MAX_RECEIPTS = 10
MAX_TOTAL_BYTES = 30 * 1024 * 1024
# A receipt is a photo of a paper slip, not a poster. The bounds stop a small
# compressed file from expanding into a large decode in the worker.
MAX_IMAGE_PIXELS = 40_000_000
MAX_PDF_PAGES = 50
# Pillow identifies the content itself, so a BMP named .jpg would otherwise pass
# the extension check and be served later as image/jpeg.
IMAGE_FORMATS = frozenset({"JPEG", "PNG", "GIF", "WEBP"})
ALLOWED_RECEIPT_TYPES = _("JPEG-, PNG-, GIF- eller WebP-bilder och PDF-filer")


class MultipleFileInput(forms.FileInput):
    """File input that posts every selected file instead of only the last one."""

    allow_multiple_selected = True


class MultipleReceiptField(forms.FileField):
    """Accept up to MAX_RECEIPTS receipts and check each file's contents.

    The extension decides how the file is parsed, and the parse decides whether
    the file is accepted: the browser's Content-Type is easy to spoof and some
    devices send ``application/octet-stream`` for a perfectly good photo.
    Nothing is read into a bytes buffer, so a 10 MB upload costs a stream, not
    a second copy in memory.
    """

    default_error_messages = {
        "too_many": _("Du kan skicka med högst %(count)d kvitton per utlägg."),
        "too_large": _("Varje kvitto får vara högst %(megabytes)d MB."),
        "too_large_total": _("Kvittona får tillsammans vara högst %(megabytes)d MB."),
        "unsupported": _("Endast %(types)s är tillåtna."),
        "invalid": _("Filen är inte en giltig bild eller PDF."),
        "too_many_pixels": _("Bilden har för många pixlar. Förminska den och försök igen."),
        "too_many_pages": _("PDF:en har för många sidor."),
    }

    def __init__(self, *args, **kwargs):
        kwargs.setdefault(
            "widget",
            MultipleFileInput(
                attrs={"multiple": True, "class": "form-control", "accept": "image/*,application/pdf"},
            ),
        )
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        if not isinstance(data, (list, tuple)):
            data = [data] if data else []
        if not data:
            if self.required:
                raise ValidationError(self.error_messages["required"], code="required")
            return []
        if len(data) > MAX_RECEIPTS:
            raise ValidationError(
                self.error_messages["too_many"] % {"count": MAX_RECEIPTS},
                code="too_many",
            )
        files = []
        total = 0
        for uploaded in data:
            uploaded = super().clean(uploaded, initial)
            if uploaded.size > MAX_RECEIPT_BYTES:
                raise ValidationError(
                    self.error_messages["too_large"] % {"megabytes": MAX_RECEIPT_BYTES // (1024 * 1024)},
                    code="too_large",
                )
            total += uploaded.size
            if total > MAX_TOTAL_BYTES:
                raise ValidationError(
                    self.error_messages["too_large_total"] % {"megabytes": MAX_TOTAL_BYTES // (1024 * 1024)},
                    code="too_large_total",
                )
            self._validate_contents(uploaded)
            files.append(uploaded)
        return files

    def _validate_contents(self, uploaded) -> None:
        suffix = Path(uploaded.name).suffix.lower().lstrip(".")
        if suffix not in RECEIPT_EXTENSIONS:
            raise ValidationError(
                self.error_messages["unsupported"] % {"types": ALLOWED_RECEIPT_TYPES},
                code="unsupported",
            )
        try:
            if suffix == "pdf":
                reader = PdfReader(uploaded)
                # Force the cross-reference table to be parsed now: a truncated
                # or password-protected PDF otherwise fails only when the
                # worker tries to append it.
                page_count = len(reader.pages)
                if page_count > MAX_PDF_PAGES:
                    raise ValidationError(self.error_messages["too_many_pages"], code="too_many_pages")
            else:
                with Image.open(uploaded) as image:
                    if image.format not in IMAGE_FORMATS:
                        raise ValidationError(self.error_messages["invalid"], code="invalid")
                    width, height = image.size
                    if width * height > MAX_IMAGE_PIXELS:
                        raise ValidationError(self.error_messages["too_many_pixels"], code="too_many_pixels")
                    image.verify()
        except (OSError, ValueError, PyPdfError, Image.DecompressionBombError) as error:
            raise ValidationError(self.error_messages["invalid"], code="invalid") from error
        finally:
            uploaded.seek(0)


class ExpenseClaimForm(forms.ModelForm):
    receipts = MultipleReceiptField(
        required=True,
        label=_("Kvitton"),
        help_text=_("Du kan välja flera filer samtidigt. Varje fil får vara högst 10 MB."),
    )
    # Declared fields come first by default, which would ask for the receipts
    # before the member has described the claim.
    field_order = ["recipient_name", "description", "amount", "payment_method", "bank_account", "receipts"]

    class Meta:
        model = ExpenseClaim
        fields = ["recipient_name", "description", "amount", "payment_method", "bank_account"]
        widgets = {
            "payment_method": forms.Select(attrs={"class": "form-select"}),
            "description": forms.Textarea(attrs={"class": "form-control", "rows": 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            if name in ("payment_method", "description", "receipts"):
                continue
            field.widget.attrs.setdefault("class", "form-control")
        self.fields["amount"].widget.attrs.update({"step": "0.01", "min": "0.01", "inputmode": "decimal"})
        self.fields["bank_account"].widget.attrs.update({"placeholder": "FI21 1234 5600 0007 85"})
