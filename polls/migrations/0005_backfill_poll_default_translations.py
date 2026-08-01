from django.db import migrations, models


def backfill_poll_default_translations(apps, schema_editor):
    Choice = apps.get_model("polls", "Choice")
    Question = apps.get_model("polls", "Question")

    Choice.objects.filter(
        models.Q(choice_text_sv__isnull=True) | models.Q(choice_text_sv=""),
    ).update(choice_text_sv=models.F("choice_text"))
    Question.objects.filter(
        models.Q(question_text_sv__isnull=True) | models.Q(question_text_sv=""),
    ).update(question_text_sv=models.F("question_text"))


class Migration(migrations.Migration):
    dependencies = [
        ("polls", "0004_choice_choice_text_en_choice_choice_text_fi_and_more"),
    ]

    operations = [
        migrations.RunPython(
            backfill_poll_default_translations,
            migrations.RunPython.noop,
        ),
    ]
