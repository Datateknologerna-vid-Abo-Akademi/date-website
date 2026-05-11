from django.db import migrations


def drop_legacy_split_data(apps, schema_editor):
    Collection = apps.get_model('archive', 'Collection')

    Collection.objects.filter(type__in=['Pictures', 'Exams']).delete()

    table_name = 'archive_picture'
    if table_name in schema_editor.connection.introspection.table_names():
        schema_editor.execute(f'DROP TABLE {schema_editor.quote_name(table_name)}')


class Migration(migrations.Migration):

    dependencies = [
        ('archive', '0008_remove_picture_collection_delete_examcollection_and_more'),
    ]

    operations = [
        migrations.RunPython(drop_legacy_split_data, migrations.RunPython.noop),
    ]
