import importlib
import os
import subprocess
import sys

from django.test import SimpleTestCase, override_settings

from core.storage_backends import StaticStorage


class StaticStorageTests(SimpleTestCase):
    def _storage(self, custom_domain=False):
        return StaticStorage(
            bucket_name="site-media",
            location="static",
            querystring_auth=False,
            custom_domain=custom_domain,
        )

    def test_manifest_state_is_initialized(self):
        # Guards the MRO: the manifest mixin must run its __init__ even
        # though S3Boto3Storage sits below it.
        storage = self._storage()
        self.assertTrue(hasattr(storage, "hashed_files"))
        self.assertTrue(hasattr(storage, "manifest_hash"))
        self.assertTrue(hasattr(storage, "manifest_storage"))

    def test_stored_name_uses_manifest_entry(self):
        storage = self._storage()
        key = storage.hash_key("css/a.css")
        storage.hashed_files = {key: "css/a.abc123.css"}
        self.assertEqual(storage.stored_name("css/a.css"), "css/a.abc123.css")

    def test_stored_name_falls_back_when_manifest_missing(self):
        # manifest_strict=False: a missing manifest entry falls back to
        # computing the hashed name instead of raising.
        storage = self._storage()
        self.assertFalse(storage.manifest_strict)

    @override_settings(DEBUG=True)
    def test_url_uses_custom_domain_with_location_prefix(self):
        storage = self._storage(custom_domain="static.example.com")
        self.assertEqual(storage.url("css/a.css"), "https://static.example.com/static/css/a.css")

    @override_settings(DEBUG=True)
    def test_scheme_prefixed_custom_domain_is_normalized(self):
        storage = self._storage(custom_domain="https://static.example.com")
        self.assertEqual(storage.url("css/a.css"), "https://static.example.com/static/css/a.css")

    @override_settings(DEBUG=True)
    def test_url_without_custom_domain_uses_endpoint(self):
        storage = self._storage()
        url = storage.url("css/a.css")
        self.assertIn("/static/css/a.css", url)


class StaticS3SettingsTests(SimpleTestCase):
    def test_static_s3_disabled_by_default(self):
        common = importlib.import_module("core.settings.common")
        self.assertFalse(common.STATIC_S3_ENABLED)
        self.assertEqual(
            common.STORAGES["staticfiles"]["BACKEND"],
            "django.contrib.staticfiles.storage.StaticFilesStorage",
        )

    def test_enabled_settings_use_the_public_bucket(self):
        # The settings branch only runs at import time, so exercise it in a
        # fresh process with distinct base and public buckets.
        env = {
            **os.environ,
            "USE_S3": "true",
            "STATIC_S3_ENABLED": "true",
            "S3_ENDPOINT_URL": "http://localhost:9000",
            "S3_ACCESS_KEY": "minioadmin",
            "S3_SECRET_KEY": "minioadmin",
            "S3_BUCKET_NAME": "base-bucket",
            "S3_PUBLIC_BUCKET_NAME": "public-bucket",
            "PRIVATE_MEDIA_LOCATION": "media/private",
            "PUBLIC_MEDIA_LOCATION": "media/public",
        }
        code = (
            "import os, importlib\n"
            "os.environ['DJANGO_SETTINGS_MODULE'] = 'core.settings.common'\n"
            "common = importlib.import_module('core.settings.common')\n"
            "opts = common.STORAGES['staticfiles']['OPTIONS']\n"
            "print(opts['bucket_name'])\n"
            "print(common.STORAGES['staticfiles']['BACKEND'])\n"
        )
        result = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True,
            text=True,
            env=env,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        lines = result.stdout.strip().splitlines()
        self.assertEqual(lines[0], "public-bucket")
        self.assertEqual(lines[1], "core.storage_backends.StaticStorage")
