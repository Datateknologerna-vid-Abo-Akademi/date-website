import io
from datetime import datetime

from celery import shared_task
from django.core.files.base import ContentFile
from django.utils import timezone


@shared_task
def generate_expense_pdf(expense_id):
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import cm
    from reportlab.pdfgen import canvas
    from reportlab.lib.utils import ImageReader

    from .models import ExpenseClaim, ExpenseReceipt

    expense = ExpenseClaim.objects.prefetch_related('receipts').get(pk=expense_id)

    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    margin = 2 * cm
    y = height - margin

    def draw_line(text, x=margin, font='Helvetica', size=12, gap=0.7 * cm):
        nonlocal y
        c.setFont(font, size)
        c.drawString(x, y, text)
        y -= gap

    def spacer(amount=0.4 * cm):
        nonlocal y
        y -= amount

    # Header
    draw_line('Expense Claim / Utgiftsersättning', font='Helvetica-Bold', size=16, gap=1 * cm)
    c.setStrokeColorRGB(0, 0, 0)
    c.line(margin, y + 0.3 * cm, width - margin, y + 0.3 * cm)
    spacer(0.5 * cm)

    # Claim details
    draw_line(f'Submission date / Inlämningsdatum: {expense.submitted_at.strftime("%d.%m.%Y")}')
    draw_line(f'Recipient / Mottagare: {expense.recipient_name}')
    draw_line(f'Description / Beskrivning: {expense.description}')
    draw_line(f'Amount / Belopp: {expense.amount} EUR')
    draw_line(f'Payment method / Betalningssätt: {expense.get_payment_method_display()}')
    if expense.payment_method == ExpenseClaim.PAYMENT_BANK:
        draw_line(f'Bank account / Bankkontonummer: {expense.bank_account}')

    spacer(0.8 * cm)

    # Receipt images
    receipts = list(expense.receipts.all())
    if receipts:
        draw_line(f'Receipts / Kvitton: {len(receipts)} file(s)')
        img_width = 10 * cm
        img_height = 8 * cm
        for i, receipt in enumerate(receipts, 1):
            try:
                receipt.file.open('rb')
                img_data = receipt.file.read()
                receipt.file.close()
                img_reader = ImageReader(io.BytesIO(img_data))
                if y - img_height < margin:
                    c.showPage()
                    y = height - margin
                c.setFont('Helvetica', 10)
                c.drawString(margin, y, f'Receipt {i}:')
                y -= 0.4 * cm
                c.drawImage(img_reader, margin, y - img_height, width=img_width, height=img_height,
                            preserveAspectRatio=True, mask='auto')
                y -= img_height + 0.5 * cm
            except Exception:
                draw_line(f'Receipt {i}: [could not embed image]')

    spacer(0.5 * cm)

    # Signature section
    if y < 6 * cm:
        c.showPage()
        y = height - margin

    c.setFont('Helvetica-Bold', 11)
    c.drawString(margin, y, 'Approval / Godkännande')
    y -= 0.8 * cm

    line_length = 7 * cm
    label_x = margin
    line_x = margin + 4.5 * cm

    c.setFont('Helvetica', 11)
    c.drawString(label_x, y, 'Approved by:')
    c.line(line_x, y - 0.1 * cm, line_x + line_length, y - 0.1 * cm)
    y -= 0.8 * cm

    c.drawString(label_x, y, 'Date:')
    c.line(line_x, y - 0.1 * cm, line_x + line_length, y - 0.1 * cm)
    y -= 1.2 * cm

    c.drawString(label_x, y, 'Treasurer signature:')
    c.line(line_x, y - 0.1 * cm, line_x + line_length, y - 0.1 * cm)
    y -= 0.8 * cm

    c.drawString(label_x, y, 'Date:')
    c.line(line_x, y - 0.1 * cm, line_x + line_length, y - 0.1 * cm)

    c.save()

    pdf_bytes = buffer.getvalue()
    filename = f'expense_claim_{expense_id}_{expense.submitted_at.strftime("%Y%m%d")}.pdf'
    expense.pdf.save(filename, ContentFile(pdf_bytes), save=False)
    expense.pdf_generated_at = timezone.now()
    expense.save(update_fields=['pdf', 'pdf_generated_at'])
