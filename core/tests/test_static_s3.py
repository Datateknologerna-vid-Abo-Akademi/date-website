import os
import subprocess
import sys
import time

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

    def test_manifest_load_retries_until_upload_finishes(self):
        # A worker that boots before the release-time static upload gets an
        # empty manifest; the retry gate must keep the manifest load cheap
        # and then pick up the manifest once it appears, without a restart.
        import json
        import tempfile

        from django.core.files.base import ContentFile
        from django.core.files.storage import FileSystemStorage

        manifest = json.dumps({"paths": {"css/a.css": "css/a.abc123.css"}, "version": "1.1", "hash": "x"}).encode()
        with tempfile.TemporaryDirectory() as tmpdir:
            manifest_fs = FileSystemStorage(location=tmpdir)
            storage = StaticStorage(
                bucket_name="site-media",
                location="static",
                querystring_auth=False,
                manifest_storage=manifest_fs,
            )
            self.assertEqual(storage.hashed_files, {})

            manifest_fs.save("staticfiles.json", ContentFile(manifest))
            retry_at = storage._manifest_retry_at
            paths, _ = storage.load_manifest()
            self.assertEqual(paths, {}, "retry window must suppress the reload")
            self.assertEqual(storage._manifest_retry_at, retry_at, "suppressed loads must not move the retry")

            storage._manifest_retry_at = time.monotonic() - 1
            self.assertEqual(storage.stored_name("css/a.css"), "css/a.abc123.css")
            self.assertIn("css/a.css", storage.hashed_files)

    def test_manifest_reload_happens_at_most_once_per_interval(self):
        import json
        import tempfile

        from django.core.files.base import ContentFile
        from django.core.files.storage import FileSystemStorage

        manifest = json.dumps({"paths": {"css/a.css": "css/a.abc123.css"}, "version": "1.1", "hash": "x"}).encode()
        with tempfile.TemporaryDirectory() as tmpdir:
            manifest_fs = FileSystemStorage(location=tmpdir)
            storage = StaticStorage(
                bucket_name="site-media",
                location="static",
                querystring_auth=False,
                manifest_storage=manifest_fs,
            )
            manifest_fs.save("staticfiles.json", ContentFile(manifest))
            # Neutralize the non-strict fallback (it would hit S3 in tests).
            storage.hashed_name = lambda name, content=None, filename=None: "css/hashed.css"
            calls = []
            original_load = storage.load_manifest
            storage.load_manifest = lambda: (calls.append(1), original_load())[1]
            storage.stored_name("css/a.css")
            self.assertEqual(len(calls), 0, "retry window must suppress the reload")
            storage._manifest_retry_at = time.monotonic() - 1
            storage.stored_name("css/a.css")
            self.assertEqual(len(calls), 1, "exactly one reload after the window")
            self.assertIn("css/a.css", storage.hashed_files)

    def test_manifest_load_failure_is_logged(self):
        # A permanent failure (auth, permissions, misconfigured storage) must
        # be observable, not silently swallowed by the self-healing retry.
        import tempfile

        from django.core.files.storage import FileSystemStorage

        with tempfile.TemporaryDirectory() as tmpdir:
            manifest_fs = FileSystemStorage(location=tmpdir)
            with self.assertLogs("core.storage_backends", level="WARNING") as logs:
                storage = StaticStorage(
                    bucket_name="site-media",
                    location="static",
                    querystring_auth=False,
                    manifest_storage=manifest_fs,
                )
            self.assertEqual(storage.hashed_files, {})
            self.assertTrue(
                any("Static manifest not available" in line for line in logs.output),
                logs.output,
            )
            # The retry gate still suppresses the next load attempt.
            with self.assertNoLogs("core.storage_backends", level="WARNING"):
                storage.load_manifest()

    def test_concurrent_reload_is_serialized(self):
        # Sync Django views run in the worker threadpool; a retry boundary
        # must not stampede the S3 manifest GET.
        import json
        import tempfile
        import threading

        from django.core.files.base import ContentFile
        from django.core.files.storage import FileSystemStorage

        manifest = json.dumps({"paths": {"css/a.css": "css/a.abc123.css"}, "version": "1.1", "hash": "x"}).encode()
        with tempfile.TemporaryDirectory() as tmpdir:
            manifest_fs = FileSystemStorage(location=tmpdir)
            storage = StaticStorage(
                bucket_name="site-media",
                location="static",
                querystring_auth=False,
                manifest_storage=manifest_fs,
            )
            manifest_fs.save("staticfiles.json", ContentFile(manifest))
            storage._manifest_retry_at = time.monotonic() - 1
            storage.hashed_name = lambda name, content=None, filename=None: "css/hashed.css"
            calls = []
            original_load = storage.load_manifest
            storage.load_manifest = lambda: (calls.append(1), original_load())[1]
            barrier = threading.Barrier(8)
            results = []

            def worker():
                barrier.wait()
                results.append(storage.stored_name("css/a.css"))

            threads = [threading.Thread(target=worker) for _ in range(8)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()
            self.assertEqual(len(calls), 1, "one reload even with concurrent lookups")
            self.assertEqual(results, ["css/a.abc123.css"] * 8)


class StaticS3SettingsTests(SimpleTestCase):
    def test_static_s3_disabled_by_default(self):
        # The DEBUG branch runs at import time, so check both states in fresh
        # processes instead of depending on the test runner's env (CI sets
        # DATE_DEBUG, a bare local run does not).
        env = {**os.environ, "DATE_DEBUG": "true"}
        code = (
            "import os, importlib\n"
            "os.environ['DJANGO_SETTINGS_MODULE'] = 'core.settings.common'\n"
            "common = importlib.import_module('core.settings.common')\n"
            "print(common.STATIC_S3_ENABLED)\n"
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
        self.assertEqual(lines[0], "False")
        self.assertEqual(
            lines[1],
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
