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
        # Persistent connections (600 s) amortize setup and are safe because
        # ConnectionLifecycleMiddleware enforces the connection lifecycle on
        # the executor thread that owns the connection; without it a
        # positive CONN_MAX_AGE leaks backends under ASGI (2026-08-31).
        self.assertEqual(default_db["CONN_MAX_AGE"], 600)
        self.assertTrue(default_db["CONN_HEALTH_CHECKS"])
