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
        self.assertGreater(default_db["CONN_MAX_AGE"], 0)
        self.assertTrue(default_db["CONN_HEALTH_CHECKS"])
