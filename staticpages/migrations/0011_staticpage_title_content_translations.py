import django_ckeditor_5.fields
from django.db import migrations, models


def backfill_staticpage_page_default_translations(apps, schema_editor):
    StaticPage = apps.get_model("staticpages", "StaticPage")

    StaticPage.objects.filter(
        models.Q(title_sv__isnull=True) | models.Q(title_sv=""),
    ).update(title_sv=models.F("title"))
    StaticPage.objects.filter(
        models.Q(content_sv__isnull=True) | models.Q(content_sv=""),
    ).update(content_sv=models.F("content"))


class Migration(migrations.Migration):
    dependencies = [
        ("staticpages", "0010_backfill_staticpage_default_translations"),
    ]

    operations = [
        migrations.AddField(
            model_name="staticpage",
            name="content_en",
            field=django_ckeditor_5.fields.CKEditor5Field(blank=True, null=True, verbose_name="Innehåll"),
        ),
        migrations.AddField(
            model_name="staticpage",
            name="content_fi",
            field=django_ckeditor_5.fields.CKEditor5Field(blank=True, null=True, verbose_name="Innehåll"),
        ),
        migrations.AddField(
            model_name="staticpage",
            name="content_sv",
            field=django_ckeditor_5.fields.CKEditor5Field(blank=True, null=True, verbose_name="Innehåll"),
        ),
        migrations.AddField(
            model_name="staticpage",
            name="title_en",
            field=models.CharField(max_length=255, null=True, verbose_name="Titel"),
        ),
        migrations.AddField(
            model_name="staticpage",
            name="title_fi",
            field=models.CharField(max_length=255, null=True, verbose_name="Titel"),
        ),
        migrations.AddField(
            model_name="staticpage",
            name="title_sv",
            field=models.CharField(max_length=255, null=True, verbose_name="Titel"),
        ),
        migrations.RunPython(
            backfill_staticpage_page_default_translations,
            migrations.RunPython.noop,
        ),
    ]
