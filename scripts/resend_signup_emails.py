import time
from billing.models import EventInvoice
import sys
import os
import django

from billing.util import send_event_invoice
import csv


sys.path.append("/code")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings.date")
django.setup()


emails_filename = sys.argv[1]

with open(emails_filename, 'r') as file:
    reader = csv.DictReader(file)
    emails = [row['email_address'] for row in reader]

    invoices = EventInvoice.objects.filter(
        participant__email__in=emails).prefetch_related("participant")
    for invoice in invoices:
        send_event_invoice(invoice.participant, invoice)
        time.sleep(1.1)
