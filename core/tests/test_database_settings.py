import importlib

from django.test import SimpleTestCase


class DatabaseSettingsTests(SimpleTestCase):
    """Guards against CONN_MAX_AGE drifting back to a top-level setting.

    Django only honors connection persistence inside each database
    configuration, so the settings must be verified where they are defined.
    """

    def test_connection_settings_live_inside_default_database(self):
        common = importlib.import_module("core.settings.common")
        default_db = common.DATABASES["default"]

        self.assertIn("CONN_MAX_AGE", default_db)
        # The ASGI web tier runs each request on a per-request thread, so a
        # persistent connection is left open on a thread that asgiref then
        # destroys: it leaks PostgreSQL backends and 500s later requests.
        # 0 closes the connection at request end on the same thread.
        self.assertEqual(default_db["CONN_MAX_AGE"], 0)
        self.assertTrue(default_db["CONN_HEALTH_CHECKS"])
