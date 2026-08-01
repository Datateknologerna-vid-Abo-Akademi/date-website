from django.db import migrations, models


def backfill_news_default_translations(apps, schema_editor):
    Category = apps.get_model("news", "Category")
    Post = apps.get_model("news", "Post")

    Category.objects.filter(
        models.Q(name_sv__isnull=True) | models.Q(name_sv=""),
    ).update(name_sv=models.F("name"))
    Post.objects.filter(
        models.Q(title_sv__isnull=True) | models.Q(title_sv=""),
    ).update(title_sv=models.F("title"))
    Post.objects.filter(
        models.Q(content_sv__isnull=True) | models.Q(content_sv=""),
    ).update(content_sv=models.F("content"))


class Migration(migrations.Migration):
    dependencies = [
        ("news", "0006_category_name_en_category_name_fi_category_name_sv_and_more"),
    ]

    operations = [
        migrations.RunPython(
            backfill_news_default_translations,
            migrations.RunPython.noop,
        ),
    ]
