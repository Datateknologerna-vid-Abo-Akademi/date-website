# Generated by Django 3.1.13 on 2022-03-05 16:01

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('staticpages', '0002_auto_20200805_1027'),
    ]

    operations = [
        migrations.AddField(
            model_name='staticpage',
            name='members_only',
            field=models.BooleanField(default=False, verbose_name='Kräv inloggning'),
        ),
    ]
