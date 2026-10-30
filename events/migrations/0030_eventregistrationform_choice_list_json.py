from django.db import migrations, models


def forwards(apps, schema_editor):
    """Split each stored comma string into a list of options."""
    registration_form = apps.get_model('events', 'EventRegistrationForm')
    for question in registration_form.objects.all().iterator():
        raw = question.choice_list or ''
        question.choice_list_new = [choice.strip() for choice in str(raw).split(',') if choice.strip()]
        question.save(update_fields=['choice_list_new'])


def backwards(apps, schema_editor):
    registration_form = apps.get_model('events', 'EventRegistrationForm')
    for question in registration_form.objects.all().iterator():
        value = question.choice_list_new
        if isinstance(value, str):
            choices = [choice.strip() for choice in value.split(',') if choice.strip()]
        else:
            choices = [str(choice).strip() for choice in (value or []) if str(choice).strip()]
        question.choice_list = ','.join(choices)
        question.save(update_fields=['choice_list'])


class Migration(migrations.Migration):
    dependencies = [
        ('events', '0029_event_event_date_start_idx_and_more'),
    ]

    operations = [
        # Add a list field, copy the old strings into it, then swap the names.
        # Altering the column type in place would need a database-specific cast.
        migrations.AddField(
            model_name='eventregistrationform',
            name='choice_list_new',
            field=models.JSONField(blank=True, default=list, verbose_name='Alternativ'),
        ),
        migrations.RunPython(forwards, backwards),
        migrations.RemoveField(model_name='eventregistrationform', name='choice_list'),
        migrations.RenameField(model_name='eventregistrationform', old_name='choice_list_new', new_name='choice_list'),
    ]
