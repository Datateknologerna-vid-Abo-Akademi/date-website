from django.db import migrations


def copy_pictures(apps, schema_editor):
    Collection = apps.get_model('archive', 'Collection')
    Picture = apps.get_model('archive', 'Picture')
    Album = apps.get_model('gallery', 'Album')
    Photo = apps.get_model('gallery', 'Photo')

    for collection in Collection.objects.filter(type='Pictures').iterator():
        Album.objects.update_or_create(
            pk=collection.pk,
            defaults={
                'title': collection.title,
                'pub_date': collection.pub_date,
                'hide_for_gulis': getattr(collection, 'hide_for_gulis', False),
            },
        )

    for picture in Picture.objects.select_related('collection').filter(collection__type='Pictures').iterator():
        Photo.objects.update_or_create(
            pk=picture.pk,
            defaults={
                'album_id': picture.collection_id,
                'image': picture.image,
                'favorite': picture.favorite,
            },
        )

    if schema_editor.connection.vendor == 'postgresql':
        with schema_editor.connection.cursor() as cursor:
            cursor.execute(
                "SELECT setval(pg_get_serial_sequence(%s, 'id'), COALESCE(MAX(id), 1), MAX(id) IS NOT NULL) FROM gallery_album",
                ['gallery_album'],
            )
            cursor.execute(
                "SELECT setval(pg_get_serial_sequence(%s, 'id'), COALESCE(MAX(id), 1), MAX(id) IS NOT NULL) FROM gallery_photo",
                ['gallery_photo'],
            )


def remove_copied_pictures(apps, schema_editor):
    apps.get_model('gallery', 'Photo').objects.all().delete()
    apps.get_model('gallery', 'Album').objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ('archive', '0007_alter_publicfile_some_file'),
        ('gallery', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(copy_pictures, remove_copied_pictures),
    ]
