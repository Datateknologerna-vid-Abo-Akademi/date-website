from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('events', '0021_event_require_registration_terms'),
    ]

    operations = [
        migrations.AddField(
            model_name='event',
            name='template',
            field=models.CharField(
                blank=True,
                choices=[
                    ('', 'Normal evenemangssida'),
                    ('events/arsfest.html', 'Årsfest'),
                    ('events/baal_detail.html', 'Baal'),
                    ('events/kk100_detail.html', '100 Baal'),
                    ('events/tomtejakt.html', 'Tomtejakt'),
                    ('events/wappmiddag.html', 'Wappmiddag'),
                ],
                max_length=255,
                verbose_name='Mall',
            ),
        ),
    ]
