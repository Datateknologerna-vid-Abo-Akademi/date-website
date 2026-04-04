from django.db import migrations


def seed_archive_view_restricted(apps, schema_editor):
    Feature = apps.get_model('members', 'Feature')
    Feature.objects.get_or_create(
        codename='archive.view_restricted',
        defaults={'name': 'Visa gömt-för-gulisar-album'},
    )


class Migration(migrations.Migration):

    dependencies = [
        ('members', '0013_seed_features'),
    ]

    operations = [
        migrations.RunPython(seed_archive_view_restricted, migrations.RunPython.noop),
    ]
