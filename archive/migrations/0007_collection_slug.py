from django.db import migrations, models

class Migration(migrations.Migration):

    dependencies = [
        ('archive', '0006_auto_20221004_1958'),
    ]

    operations = [
        migrations.AddField(
            model_name='collection',
            name='slug',
            field=models.SlugField(blank=True, max_length=50, unique=True, allow_unicode=False, verbose_name='Slug'),
        ),
    ]
