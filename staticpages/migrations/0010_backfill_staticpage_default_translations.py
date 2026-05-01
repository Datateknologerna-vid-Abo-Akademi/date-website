from django.db import migrations, models


def backfill_staticpage_default_translations(apps, schema_editor):
    StaticPageNav = apps.get_model("staticpages", "StaticPageNav")
    StaticUrl = apps.get_model("staticpages", "StaticUrl")

    StaticPageNav.objects.filter(
        models.Q(category_name_sv__isnull=True) | models.Q(category_name_sv=""),
    ).update(category_name_sv=models.F("category_name"))
    StaticUrl.objects.filter(
        models.Q(title_sv__isnull=True) | models.Q(title_sv=""),
    ).update(title_sv=models.F("title"))


class Migration(migrations.Migration):
    dependencies = [
        ("staticpages", "0009_staticpagenav_category_name_en_and_more"),
    ]

    operations = [
        migrations.RunPython(
            backfill_staticpage_default_translations,
            migrations.RunPython.noop,
        ),
    ]
