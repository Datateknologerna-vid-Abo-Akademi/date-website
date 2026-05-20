import csv
import os
import sys
from io import StringIO

import django

sys.path.append("/code")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings.date")
django.setup()

from members.models import Member, SubscriptionPayment

with StringIO() as csvfile:
    fieldnames = ['member_username', 'member_name', 'payment_date', 'expires', 'active']
    writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

    writer.writeheader()
    for payment in SubscriptionPayment.objects.all():
        member = Member.objects.filter(id=payment.member_id).first()
        writer.writerow(
            {
                'member_username': member,
                'member_name': member.full_name,
                'payment_date': payment.date_paid,
                'expires': payment.expires,
                'active': payment.is_active,
            }
        )

    print(csvfile.getvalue())
