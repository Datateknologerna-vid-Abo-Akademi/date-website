from django.db import migrations, models


def backfill_ctf_default_translations(apps, schema_editor):
    Ctf = apps.get_model("ctf", "Ctf")

    Ctf.objects.filter(
        models.Q(title_sv__isnull=True) | models.Q(title_sv=""),
    ).update(title_sv=models.F("title"))
    Ctf.objects.filter(
        models.Q(content_sv__isnull=True) | models.Q(content_sv=""),
    ).update(content_sv=models.F("content"))


class Migration(migrations.Migration):
    dependencies = [
        ("ctf", "0005_ctf_content_en_ctf_content_fi_ctf_content_sv_and_more"),
    ]

    operations = [
        migrations.RunPython(
            backfill_ctf_default_translations,
            migrations.RunPython.noop,
        ),
    ]
