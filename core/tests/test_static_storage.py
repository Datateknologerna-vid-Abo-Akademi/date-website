from django.core.files.base import ContentFile
from django.test import SimpleTestCase

from core.storage_backends import NonStrictManifestStaticFilesStorage


class NonStrictManifestStorageTests(SimpleTestCase):
    def test_stored_name_uses_manifest_entry_when_present(self):
        storage = NonStrictManifestStaticFilesStorage()
        storage.hashed_files = {
            "date/css/homepage.css": "date/css/homepage.4f176ff3067f.css",
        }
        self.assertEqual(
            storage.stored_name("date/css/homepage.css"),
            "date/css/homepage.4f176ff3067f.css",
        )

    def test_stored_name_computes_hash_when_manifest_lacks_entry(self):
        storage = NonStrictManifestStaticFilesStorage()
        storage.hashed_files = {}
        storage.save("x.css", ContentFile("body {}"))
        name = storage.stored_name("x.css")
        self.assertNotEqual(name, "x.css")
        self.assertIn("x.", name)

    def test_missing_file_still_raises(self):
        # manifest_strict=False only relaxes manifest lookups; references to
        # files that do not exist must keep failing so collectstatic cannot
        # silently ship broken asset references.
        storage = NonStrictManifestStaticFilesStorage()
        with self.assertRaises(ValueError):
            storage.stored_name("does-not-exist.css")
