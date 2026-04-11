import archive.models
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('archive', '0007_alter_publicfile_some_file'),
    ]

    operations = [
        migrations.AlterField(
            model_name='picture',
            name='image',
            field=models.ImageField(blank=True, null=True, upload_to=archive.models.upload_to),
        ),
        migrations.AddField(
            model_name='picture',
            name='cloudflare_image_id',
            field=models.CharField(blank=True, max_length=64, null=True, unique=True),
        ),
        migrations.AddField(
            model_name='picture',
            name='cloudflare_variant_url',
            field=models.URLField(blank=True, max_length=500, null=True),
        ),
        migrations.AddField(
            model_name='picture',
            name='original_filename',
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name='picture',
            name='upload_provider',
            field=models.CharField(choices=[('local', 'Local'), ('cloudflare', 'Cloudflare')], default='local', max_length=32),
        ),
    ]
