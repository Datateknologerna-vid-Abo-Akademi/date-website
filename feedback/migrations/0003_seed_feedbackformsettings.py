from django.db import migrations

# Copy of feedback.models.DEFAULT_INTRO_TEXT. Migrations must not import the
# live model module, whose constant can drift from the schema this migration
# runs against. The seed fills the Swedish column only; the en/fi columns stay
# at the field default ('') so modeltranslation falls back to sv until an
# editor translates them. See docs/dev/feedback.md.
DEFAULT_INTRO_TEXT = 'Har du synpunkter eller feedback? Skriv gärna till oss här.'


def seed_feedback_form_settings(apps, schema_editor):
    FeedbackFormSettings = apps.get_model('feedback', 'FeedbackFormSettings')
    if not FeedbackFormSettings.objects.exists():
        FeedbackFormSettings.objects.create(intro_text_sv=DEFAULT_INTRO_TEXT)


class Migration(migrations.Migration):

    dependencies = [
        ('feedback', '0002_feedbackformsettings'),
    ]

    operations = [
        # Reversing deliberately leaves the row alone: an editor may have
        # rewritten the text by then, and rolling the migration back should not
        # throw that away.
        migrations.RunPython(seed_feedback_form_settings, migrations.RunPython.noop),
    ]
