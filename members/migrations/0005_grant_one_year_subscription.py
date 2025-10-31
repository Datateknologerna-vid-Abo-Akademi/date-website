from datetime import timedelta
from decimal import Decimal

from django.utils import timezone
from django.db import migrations


def grant_one_year_subscriptions(apps, schema_editor):
    Subscription = apps.get_model('members', 'Subscription')
    SubscriptionPayment = apps.get_model('members', 'SubscriptionPayment')
    Member = apps.get_model('members', 'Member')

    subscription, created = Subscription.objects.get_or_create(
        name='Legacy Migration Subscription',
        defaults={
            'does_expire': True,
            'renewal_scale': 'year',
            'renewal_period': 1,
            'price': Decimal('0.00'),
        },
    )

    if not created:
        updated = False
        if not subscription.does_expire:
            subscription.does_expire = True
            updated = True
        if subscription.renewal_scale != 'year':
            subscription.renewal_scale = 'year'
            updated = True
        if subscription.renewal_period != 1:
            subscription.renewal_period = 1
            updated = True
        if subscription.price != Decimal('0.00'):
            subscription.price = Decimal('0.00')
            updated = True
        if updated:
            subscription.save(update_fields=['does_expire', 'renewal_scale', 'renewal_period', 'price'])

    today = timezone.now().date()
    expires = today + timedelta(days=365)

    for member in Member.objects.all():
        existing_payment = (
            SubscriptionPayment.objects.filter(member=member)
            .order_by('-date_expires')
            .first()
        )
        if existing_payment and (
            existing_payment.date_expires is None or existing_payment.date_expires >= today
        ):
            continue
        SubscriptionPayment.objects.create(
            member=member,
            subscription=subscription,
            date_paid=today,
            date_expires=expires,
            amount_paid=Decimal('0.00'),
        )


class Migration(migrations.Migration):

    dependencies = [
        ('members', '0004_alumniemailrecipient_alumnisignup_functionaryrole_and_more'),
    ]

    operations = [
        migrations.RunPython(grant_one_year_subscriptions, migrations.RunPython.noop),
    ]
