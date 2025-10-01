import time
import datetime
import sys
import os
import django

import csv


sys.path.append("/code")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings.on")
django.setup()

from billing.models import EventInvoice
from billing.util import send_event_invoice

emails_filename = sys.argv[1]

with open(emails_filename, 'r') as file:
    reader = csv.DictReader(file)
    emails = [row['email_address'] for row in reader]

    invoices = EventInvoice.objects.filter(
        participant__email__in=emails, due_date__gte=datetime.datetime.now()).prefetch_related("participant")
    for invoice in invoices:
        send_event_invoice(invoice.participant, invoice)
        time.sleep(1.1)
