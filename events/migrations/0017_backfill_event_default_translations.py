from django.db import migrations, models


def backfill_event_default_translations(apps, schema_editor):
    Event = apps.get_model("events", "Event")

    Event.objects.filter(
        models.Q(title_sv__isnull=True) | models.Q(title_sv=""),
    ).update(title_sv=models.F("title"))
    Event.objects.filter(
        models.Q(content_sv__isnull=True) | models.Q(content_sv=""),
    ).update(content_sv=models.F("content"))


class Migration(migrations.Migration):
    dependencies = [
        ("events", "0016_event_content_en_event_content_fi_event_content_sv_and_more"),
    ]

    operations = [
        migrations.RunPython(
            backfill_event_default_translations,
            migrations.RunPython.noop,
        ),
    ]
