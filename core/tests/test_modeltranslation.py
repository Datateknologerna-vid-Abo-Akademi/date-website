from django.test import SimpleTestCase, override_settings

from core.modeltranslation import get_translation_languages


class ModeltranslationLanguageTests(SimpleTestCase):
    @override_settings(
        LANGUAGES=(("sv", "Svenska"), ("en", "English")),
        MODELTRANSLATION_LANGUAGES=("sv", "en", "fi"),
    )
    def test_uses_stable_schema_languages_when_site_languages_are_subset(self):
        self.assertEqual(get_translation_languages(), ("sv", "en", "fi"))

    @override_settings(
        LANGUAGES=(("sv", "Svenska"),),
        MODELTRANSLATION_LANGUAGES=("sv", "en", "fi"),
    )
    def test_uses_stable_schema_languages_when_language_features_disabled(self):
        self.assertEqual(get_translation_languages(), ("sv", "en", "fi"))

    @override_settings(
        LANGUAGES=(("sv", "Svenska"), ("en", "English")),
        MODELTRANSLATION_LANGUAGES=(),
    )
    def test_falls_back_to_site_languages_when_schema_languages_missing(self):
        self.assertEqual(get_translation_languages(), ("sv", "en"))
