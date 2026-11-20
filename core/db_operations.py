"""Migration operations shared by the project's index migrations."""

from django.contrib.postgres.operations import AddIndexConcurrently as _AddIndexConcurrently


class AddIndexConcurrently(_AddIndexConcurrently):
    """Create an index without locking writes on PostgreSQL.

    The test suite runs on SQLite, which has no concurrent index creation.
    Skip the database operation there: the migration state still records the
    index, and production (PostgreSQL) creates it concurrently.
    """

    def database_forwards(self, app_label, schema_editor, from_state, to_state):
        if schema_editor.connection.vendor != 'postgresql':
            return
        super().database_forwards(app_label, schema_editor, from_state, to_state)

    def database_backwards(self, app_label, schema_editor, from_state, to_state):
        if schema_editor.connection.vendor != 'postgresql':
            return
        super().database_backwards(app_label, schema_editor, from_state, to_state)
