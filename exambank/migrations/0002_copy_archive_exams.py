from django.db import migrations


def copy_exams(apps, schema_editor):
    Collection = apps.get_model('archive', 'Collection')
    Document = apps.get_model('archive', 'Document')
    ExamArchive = apps.get_model('exambank', 'ExamArchive')
    ExamFile = apps.get_model('exambank', 'ExamFile')

    for collection in Collection.objects.filter(type='Exams').iterator():
        ExamArchive.objects.update_or_create(
            pk=collection.pk,
            defaults={
                'title': collection.title,
                'pub_date': collection.pub_date,
                'hide_for_gulis': getattr(collection, 'hide_for_gulis', False),
            },
        )

    for document in Document.objects.select_related('collection').filter(collection__type='Exams').iterator():
        ExamFile.objects.update_or_create(
            pk=document.pk,
            defaults={
                'archive_id': document.collection_id,
                'title': document.title,
                'document': document.document,
            },
        )

    if schema_editor.connection.vendor == 'postgresql':
        with schema_editor.connection.cursor() as cursor:
            cursor.execute(
                "SELECT setval(pg_get_serial_sequence(%s, 'id'), COALESCE(MAX(id), 1), MAX(id) IS NOT NULL) FROM exambank_examarchive",
                ['exambank_examarchive'],
            )
            cursor.execute(
                "SELECT setval(pg_get_serial_sequence(%s, 'id'), COALESCE(MAX(id), 1), MAX(id) IS NOT NULL) FROM exambank_examfile",
                ['exambank_examfile'],
            )


def remove_copied_exams(apps, schema_editor):
    apps.get_model('exambank', 'ExamFile').objects.all().delete()
    apps.get_model('exambank', 'ExamArchive').objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ('archive', '0007_alter_publicfile_some_file'),
        ('exambank', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(copy_exams, remove_copied_exams),
    ]
