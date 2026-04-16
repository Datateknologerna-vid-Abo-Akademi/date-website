from django.test import SimpleTestCase, override_settings

from core.modeltranslation import get_translation_languages


class ModeltranslationLanguageTests(SimpleTestCase):
    @override_settings(LANGUAGES=(("sv", "Svenska"), ("en", "English")))
    def test_uses_date_language_subset(self):
        self.assertEqual(get_translation_languages(), ("sv", "en"))

    @override_settings(LANGUAGES=(("sv", "Svenska"), ("en", "English"), ("fi", "Suomi")))
    def test_keeps_finnish_for_three_language_sites(self):
        self.assertEqual(get_translation_languages(), ("sv", "en", "fi"))

    @override_settings(LANGUAGES=())
    def test_falls_back_to_schema_languages_when_languages_missing(self):
        with self.settings(MODELTRANSLATION_LANGUAGES=("sv", "en", "fi")):
            self.assertEqual(get_translation_languages(), ("sv", "en", "fi"))
