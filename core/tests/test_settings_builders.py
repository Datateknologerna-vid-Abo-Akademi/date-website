import importlib

from django.test import SimpleTestCase


class SettingsBuilderTests(SimpleTestCase):
    """Guards the shared template/static builders' precedence rules."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.common = importlib.import_module("core.settings.common")

    def test_plain_variant_dirs(self):
        templates = self.common.build_templates("date")
        self.assertEqual(
            templates[0]["DIRS"],
            ["templates/date", "templates/common", "templates/common/members"],
        )
        self.assertTrue(templates[0]["APP_DIRS"])

    def test_parent_variants_precede_common(self):
        templates = self.common.build_templates("biocum", parent_variants=("date",))
        self.assertEqual(
            templates[0]["DIRS"],
            ["templates/biocum", "templates/date", "templates/common", "templates/common/members"],
        )

    def test_common_context_processors_are_preserved(self):
        templates = self.common.build_templates("date")
        self.assertEqual(templates[0]["OPTIONS"]["context_processors"], self.common.COMMON_CONTEXT_PROCESSORS)

    def test_static_dirs_do_not_inherit_parents(self):
        # Template inheritance must not leak into static dirs.
        static_dirs = self.common.build_static_dirs("sf", parent_variants=("date",))
        self.assertEqual(
            static_dirs,
            [
                self.common.os.path.join(self.common.BASE_DIR, "static/sf"),
                self.common.os.path.join(self.common.BASE_DIR, "static/date"),
                self.common.os.path.join(self.common.BASE_DIR, "static/common"),
            ],
        )

    def test_plain_static_dirs(self):
        static_dirs = self.common.build_static_dirs("kk")
        self.assertEqual(
            static_dirs,
            [
                self.common.os.path.join(self.common.BASE_DIR, "static/kk"),
                self.common.os.path.join(self.common.BASE_DIR, "static/common"),
            ],
        )
