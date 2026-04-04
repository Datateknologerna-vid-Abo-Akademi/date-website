from django.db import migrations


def seed_features(apps, schema_editor):
    Feature = apps.get_model('members', 'Feature')
    for codename, name in [
        ('archive.view',    'Visa foto/dokument/tentarkiv'),
        ('archive.upload',  'Ladda upp bilder till arkivet'),
        ('polls.vote',      'Rösta i omröstningar'),
        ('events.register', 'Anmäla sig till evenemang'),
    ]:
        Feature.objects.get_or_create(codename=codename, defaults={'name': name})


class Migration(migrations.Migration):

    dependencies = [
        ('members', '0012_feature_signingkey_membershiptypepermission'),
    ]

    operations = [
        migrations.RunPython(seed_features, migrations.RunPython.noop),
    ]
