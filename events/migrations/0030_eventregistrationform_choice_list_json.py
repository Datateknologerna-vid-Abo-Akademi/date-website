from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('events', '0029_event_event_date_start_idx_and_more'),
    ]

    operations = [
        # Change the Python field name without touching the live text column.
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AlterField(
                    model_name='eventregistrationform',
                    name='choice_list',
                    field=models.CharField(
                        blank=True, db_column='choice_list', max_length=255, verbose_name='Alternativ'
                    ),
                ),
                migrations.RenameField(
                    model_name='eventregistrationform', old_name='choice_list', new_name='legacy_choice_list'
                ),
            ],
        ),
        migrations.AddField(
            model_name='eventregistrationform',
            name='choice_list',
            field=models.JSONField(blank=True, db_column='choice_list_json', null=True, verbose_name='Alternativ'),
        ),
    ]
