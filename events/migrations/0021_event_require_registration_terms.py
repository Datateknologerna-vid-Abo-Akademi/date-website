from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('events', '0020_backfill_blank_event_slugs'),
    ]

    operations = [
        migrations.AddField(
            model_name='event',
            name='require_registration_terms',
            field=models.BooleanField(
                default=True,
                verbose_name='Kräv godkännande av anmälningsvillkor',
            ),
        ),
    ]
