from io import StringIO

from django.core.management import call_command
from django.test import SimpleTestCase


class StaticOverridesReportTests(SimpleTestCase):
    def test_static_override_is_reported(self):
        out = StringIO()
        call_command("static_overrides_report", "--tree", "static", stdout=out)
        result = out.getvalue()
        self.assertIn("static override", result)
        self.assertIn("events/css/style.css", result)

    def test_shared_identical_files_are_not_reported(self):
        # Files identical across trees (copied but unchanged) are fine.
        out = StringIO()
        call_command("static_overrides_report", "--tree", "static", stdout=out)
        result = out.getvalue()
        self.assertNotIn("date-root.css", result)

    def test_template_multi_variant_definitions_are_reported(self):
        out = StringIO()
        call_command("static_overrides_report", "--tree", "templates", stdout=out)
        result = out.getvalue()
        self.assertIn("template defined in multiple variants", result)
        self.assertIn("news/index.html", result)
