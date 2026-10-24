"""Index the admin log for the LogEntry changelist's default ordering.

``django.contrib.admin`` owns the ``django_admin_log`` table, so the index
cannot be declared in a model's ``Meta.indexes``. The migration runs outside a
transaction because ``CREATE INDEX CONCURRENTLY`` refuses to run inside one,
and non-PostgreSQL databases (the test suite uses SQLite) skip the statement.
"""

from django.db import migrations


def create_action_time_index(apps, schema_editor):
    if schema_editor.connection.vendor != 'postgresql':
        return
    schema_editor.execute(
        'CREATE INDEX CONCURRENTLY IF NOT EXISTS django_admin_log_action_time_idx '
        'ON django_admin_log (action_time)'
    )


def drop_action_time_index(apps, schema_editor):
    if schema_editor.connection.vendor != 'postgresql':
        return
    schema_editor.execute('DROP INDEX CONCURRENTLY IF EXISTS django_admin_log_action_time_idx')


class Migration(migrations.Migration):

    atomic = False

    dependencies = [
        ('admin', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(create_action_time_index, drop_action_time_index),
    ]
