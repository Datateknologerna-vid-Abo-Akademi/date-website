from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):

    dependencies = [
        ('staticpages', '0013_staticpage_image_staticpage_s3_image'),
    ]

    operations = [
        migrations.AddField(
            model_name='staticurl',
            name='parent',
            field=models.ForeignKey(
                blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='children', to='staticpages.staticurl'
            ),
        ),
        migrations.AlterField(
            model_name='staticurl',
            name='url',
            field=models.CharField(max_length=200, blank=True, verbose_name='Url'),
        ),
    ]