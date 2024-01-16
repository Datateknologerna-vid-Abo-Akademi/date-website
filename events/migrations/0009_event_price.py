# Generated by Django 3.1.13 on 2023-04-11 15:29

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('events', '0008_eventregistrationform_price'),
    ]

    operations = [
        migrations.AddField(
            model_name='event',
            name='price',
            field=models.DecimalField(decimal_places=2, default=0, max_digits=10, verbose_name='Pris'),
        ),
    ]