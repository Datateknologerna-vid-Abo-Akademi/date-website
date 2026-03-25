import io

from celery import shared_task
from django.core.files.base import ContentFile
from django.utils import timezone


@shared_task
def generate_expense_pdf(expense_id):
    from pypdf import PdfWriter, PdfReader
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import cm
    from reportlab.pdfgen import canvas
    from reportlab.lib.utils import ImageReader

    from django.conf import settings as django_settings
    from .models import ExpenseClaim

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
    association_name = django_settings.CONTENT_VARIABLES.get('ASSOCIATION_NAME_FULL', '')
    if association_name:
        draw_line(association_name, font='Helvetica', size=11, gap=0.6 * cm)
    draw_line('Kostnadsersättning', font='Helvetica-Bold', size=16, gap=1 * cm)
    c.setStrokeColorRGB(0, 0, 0)
    c.line(margin, y + 0.3 * cm, width - margin, y + 0.3 * cm)
    spacer(0.5 * cm)

    # Claim details
    draw_line(f'Inlämningsdatum: {expense.submitted_at.strftime("%d.%m.%Y")}')
    draw_line(f'Mottagare: {expense.recipient_name}')
    draw_line(f'Beskrivning: {expense.description}')
    draw_line(f'Belopp: {expense.amount} EUR')
    draw_line(f'Betalningssätt: {expense.get_payment_method_display()}')
    if expense.payment_method == ExpenseClaim.PAYMENT_BANK:
        draw_line(f'Bankkontonummer: {expense.bank_account}')

    spacer(0.8 * cm)

    receipts = list(expense.receipts.all())
    if receipts:
        draw_line(f'Kvitton: {len(receipts)} fil(er)')

    spacer(0.5 * cm)

    # Signature section
    if y < 6 * cm:
        c.showPage()
        y = height - margin

    c.setFont('Helvetica-Bold', 11)
    c.drawString(margin, y, 'Godkännande')
    y -= 0.8 * cm

    line_length = 7 * cm
    label_x = margin
    line_x = margin + 4.5 * cm

    c.setFont('Helvetica', 11)
    c.drawString(label_x, y, 'Godkänd av:')
    c.line(line_x, y - 0.1 * cm, line_x + line_length, y - 0.1 * cm)
    y -= 0.8 * cm

    c.drawString(label_x, y, 'Datum:')
    c.line(line_x, y - 0.1 * cm, line_x + line_length, y - 0.1 * cm)
    y -= 1.2 * cm

    c.drawString(label_x, y, 'Kassörens signatur:')
    c.line(line_x, y - 0.1 * cm, line_x + line_length, y - 0.1 * cm)
    y -= 0.8 * cm

    c.drawString(label_x, y, 'Datum:')
    c.line(line_x, y - 0.1 * cm, line_x + line_length, y - 0.1 * cm)

    # Read all receipt data once and detect type by attempting PDF parse
    receipt_data = []
    for receipt in receipts:
        receipt.file.open('rb')
        data = receipt.file.read()
        receipt.file.close()
        try:
            PdfReader(io.BytesIO(data))
            is_pdf = True
        except Exception:
            is_pdf = False
        receipt_data.append((receipt, data, is_pdf))

    # Image receipts embedded as full pages in the reportlab canvas
    image_num = 0
    for receipt, data, is_pdf in receipt_data:
        if is_pdf:
            continue
        image_num += 1
        c.showPage()
        try:
            img_reader = ImageReader(io.BytesIO(data))
            usable_width = width - 2 * margin
            usable_height = height - 2 * margin
            c.setFont('Helvetica-Bold', 12)
            c.drawString(margin, height - margin, f'Kvitto {image_num}')
            c.drawImage(img_reader, margin, margin, width=usable_width, height=usable_height - 1 * cm,
                        preserveAspectRatio=True, anchor='n', mask='auto')
        except Exception:
            c.setFont('Helvetica', 11)
            c.drawString(margin, height / 2, f'Kvitto {image_num}: [kunde inte bädda in bild]')

    c.save()

    # Merge with pypdf: main doc (with image pages) + PDF receipts appended
    writer = PdfWriter()
    writer.append(PdfReader(io.BytesIO(buffer.getvalue())))

    pdf_num = image_num
    for receipt, data, is_pdf in receipt_data:
        if not is_pdf:
            continue
        pdf_num += 1
        try:
            writer.append(PdfReader(io.BytesIO(data)))
        except Exception:
            pass

    out = io.BytesIO()
    writer.write(out)
    pdf_bytes = out.getvalue()

    filename = f'kostnadsersattning_{expense_id}_{expense.submitted_at.strftime("%Y%m%d")}.pdf'
    expense.pdf.save(filename, ContentFile(pdf_bytes), save=False)
    expense.pdf_generated_at = timezone.now()
    expense.save(update_fields=['pdf', 'pdf_generated_at'])
