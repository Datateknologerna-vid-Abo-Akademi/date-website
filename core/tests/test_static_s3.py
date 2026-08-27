import importlib

from django.test import SimpleTestCase

from core.storage_backends import StaticStorage


class StaticStorageTests(SimpleTestCase):
    def _storage(self, custom_domain=False):
        return StaticStorage(
            bucket_name="site-media",
            location="static",
            querystring_auth=False,
            custom_domain=custom_domain,
        )

    def test_url_uses_custom_domain_with_location_prefix(self):
        storage = self._storage(custom_domain="static.example.com")
        self.assertEqual(storage.url("css/a.css"), "https://static.example.com/static/css/a.css")

    def test_scheme_prefixed_custom_domain_is_normalized(self):
        storage = self._storage(custom_domain="https://static.example.com")
        self.assertEqual(storage.url("css/a.css"), "https://static.example.com/static/css/a.css")

    def test_url_without_custom_domain_uses_endpoint(self):
        storage = self._storage()
        url = storage.url("css/a.css")
        self.assertIn("/static/css/a.css", url)

    def test_manifest_storage_with_vendored_asset_tolerance(self):
        storage = self._storage()
        self.assertTrue(hasattr(storage, "stored_name"))
        self.assertFalse(storage.manifest_strict)


class StaticS3SettingsTests(SimpleTestCase):
    def test_static_s3_disabled_by_default(self):
        common = importlib.import_module("core.settings.common")
        self.assertFalse(common.STATIC_S3_ENABLED)
        self.assertEqual(
            common.STORAGES["staticfiles"]["BACKEND"],
            "django.contrib.staticfiles.storage.StaticFilesStorage",
        )
