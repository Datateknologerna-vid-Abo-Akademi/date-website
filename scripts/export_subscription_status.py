import sys
import os
from io import StringIO

import django
import csv

sys.path.append("/code")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings.date")
django.setup()

from members.models import SubscriptionPayment, Member

with StringIO() as csvfile:
    fieldnames = ['member_username', 'member_name', 'payment_date', 'expires', 'active']
    writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

    writer.writeheader()
    for payment in SubscriptionPayment.objects.all():
        member = Member.objects.filter(id=payment.member_id).first()
        writer.writerow({'member_username': member, 'member_name': member.full_name, 'payment_date': payment.date_paid, 'expires': payment.expires, 'active': payment.is_active})

    print(csvfile.getvalue())
