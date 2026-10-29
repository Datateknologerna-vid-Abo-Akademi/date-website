import io
import logging

from celery import shared_task
from django.conf import settings
from django.core.files.base import ContentFile
from django.utils import timezone
from pypdf import PdfReader, PdfWriter
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

logger = logging.getLogger("date")

PAGE_WIDTH, PAGE_HEIGHT = A4
BODY_FONT = "Helvetica"
BODY_SIZE = 12


@shared_task
def generate_expense_pdf(expense_id: int) -> None:
    """Render the claim and its receipts into the PDF the treasurer signs."""
    from .models import ExpenseClaim

    try:
        expense = ExpenseClaim.objects.prefetch_related("receipts").get(pk=expense_id)
    except ExpenseClaim.DoesNotExist:
        logger.warning("Expense claim %s disappeared before its PDF was generated", expense_id)
        return

    document = _build_document(expense)
    previous_name = expense.pdf.name if expense.pdf else ""
    previous_storage = expense.pdf.storage if expense.pdf else None
    expense.pdf.save(f"kostnadsersattning-{expense.pk}.pdf", ContentFile(document), save=False)
    expense.pdf_generated_at = timezone.now()
    try:
        expense.save(update_fields=["pdf", "pdf_generated_at"])
    except Exception:
        # Keep the model pointing at the old object. The replacement may be an
        # orphan in storage, but the previous working PDF is still there.
        expense.pdf.name = previous_name
        raise
    if previous_name and previous_storage is not None:
        try:
            previous_storage.delete(previous_name)
        except Exception:
            logger.exception("Could not delete the previous PDF for expense claim %s", expense.pk)


def _sanitize(text) -> str:
    """Drop characters reportlab's built-in Latin-1 fonts cannot draw."""
    return str(text).encode("latin-1", "replace").decode("latin-1")


def _wrap(canvas_, text, font: str, size: int, max_width: float) -> list[str]:
    """Wrap on words using reportlab's own string widths, not character counts."""
    lines: list[str] = []
    current = ""
    for word in _sanitize(text).split():
        candidate = f"{current} {word}".strip()
        if not current or canvas_.stringWidth(candidate, font, size) <= max_width:
            current = candidate
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines or [""]


def _build_document(expense) -> bytes:
    buffer = io.BytesIO()
    canvas_ = canvas.Canvas(buffer, pagesize=A4)
    margin = 2 * cm
    content_width = PAGE_WIDTH - 2 * margin
    y = PAGE_HEIGHT - margin

    def draw_line(text, *, x=margin, font=BODY_FONT, size=BODY_SIZE, gap=0.7 * cm):
        nonlocal y
        if y < margin:
            canvas_.showPage()
            y = PAGE_HEIGHT - margin
        canvas_.setFont(font, size)
        canvas_.drawString(x, y, _sanitize(text))
        y -= gap

    def draw_paragraph(text, *, font=BODY_FONT, size=BODY_SIZE, gap=0.7 * cm):
        for line in _wrap(canvas_, text, font, size, content_width):
            draw_line(line, font=font, size=size, gap=gap)

    def spacer(amount=0.4 * cm):
        nonlocal y
        y -= amount

    association_name = settings.CONTENT_VARIABLES.get("ASSOCIATION_NAME_FULL", "")
    if association_name:
        draw_line(association_name, size=11, gap=0.6 * cm)
    draw_line(f"Kostnadsersättning #{expense.pk}", font="Helvetica-Bold", size=16, gap=1 * cm)
    canvas_.setStrokeColorRGB(0, 0, 0)
    canvas_.line(margin, y + 0.3 * cm, PAGE_WIDTH - margin, y + 0.3 * cm)
    spacer(0.5 * cm)

    submitted_at = timezone.localtime(expense.submitted_at)
    draw_line(f"Inlämningsdatum: {submitted_at:%d.%m.%Y}")
    draw_paragraph(f"Mottagare: {expense.recipient_name}")
    draw_paragraph(f"Beskrivning: {expense.description}")
    draw_line(f"Belopp: {expense.amount} EUR")
    draw_line(f"Betalningssätt: {expense.get_payment_method_display()}")
    if expense.payment_method == expense.PAYMENT_BANK:
        draw_line(f"Bankkontonummer: {expense.bank_account}")

    spacer(0.8 * cm)
    receipts = list(expense.receipts.all())
    if receipts:
        draw_line(f"Kvitton: {len(receipts)} fil(er)")

    spacer(0.5 * cm)

    if y < 6 * cm:
        canvas_.showPage()
        y = PAGE_HEIGHT - margin

    canvas_.setFont("Helvetica-Bold", 11)
    canvas_.drawString(margin, y, "Godkännande")
    y -= 0.8 * cm

    line_length = 7 * cm
    line_x = margin + 4.5 * cm

    canvas_.setFont(BODY_FONT, 11)
    for label in ("Godkänd av:", "Datum:", "Kassörens signatur:", "Datum:"):
        canvas_.drawString(margin, y, label)
        canvas_.line(line_x, y - 0.1 * cm, line_x + line_length, y - 0.1 * cm)
        y -= 1.2 * cm if label == "Datum:" else 0.8 * cm

    image_number = 0
    for receipt in receipts:
        if receipt.is_pdf:
            continue
        image_number += 1
        canvas_.showPage()
        canvas_.setFont("Helvetica-Bold", 12)
        canvas_.drawString(margin, PAGE_HEIGHT - margin, f"Kvitto {image_number}")
        try:
            with receipt.file.open("rb") as file_handle:
                data = file_handle.read()
            image = ImageReader(io.BytesIO(data))
            canvas_.drawImage(
                image,
                margin,
                margin,
                width=content_width,
                height=PAGE_HEIGHT - 2 * margin - 1 * cm,
                preserveAspectRatio=True,
                anchor="n",
                mask="auto",
            )
        except Exception:
            logger.exception("Could not embed image receipt %s on claim %s", receipt.pk, expense.pk)
            canvas_.setFont(BODY_FONT, 11)
            canvas_.drawString(margin, PAGE_HEIGHT / 2, f"Kvitto {image_number}: [kunde inte bädda in bild]")

    canvas_.save()

    writer = PdfWriter()
    writer.append(PdfReader(io.BytesIO(buffer.getvalue())))
    for receipt in receipts:
        if not receipt.is_pdf:
            continue
        try:
            with receipt.file.open("rb") as file_handle:
                writer.append(PdfReader(io.BytesIO(file_handle.read())))
        except Exception:
            logger.exception("Could not append PDF receipt %s on claim %s", receipt.pk, expense.pk)
            writer.append(_failure_page(receipt.pk))

    output = io.BytesIO()
    writer.write(output)
    return output.getvalue()


def _failure_page(receipt_id: int) -> PdfReader:
    """A readable stand-in page so a bad receipt cannot silently shrink the PDF."""
    buffer = io.BytesIO()
    canvas_ = canvas.Canvas(buffer, pagesize=A4)
    canvas_.setFont(BODY_FONT, 12)
    canvas_.drawString(2 * cm, PAGE_HEIGHT / 2, f"Kvitto #{receipt_id} kunde inte bifogas i PDF:en.")
    canvas_.save()
    return PdfReader(io.BytesIO(buffer.getvalue()))
