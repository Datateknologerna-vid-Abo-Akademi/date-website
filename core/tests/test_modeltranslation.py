from pathlib import Path

from django.conf import settings
from django.contrib import admin
from django.test import RequestFactory, SimpleTestCase, override_settings

from core.admin import LanguageTabbedTranslationAdmin
from core.modeltranslation import get_translation_languages
from functionaries.admin import FunctionaryRoleAdmin
from functionaries.models import FunctionaryRole
from publications.admin import PDFFileAdmin


class ModeltranslationLanguageTests(SimpleTestCase):
    @override_settings(LANGUAGES=(("sv", "Svenska"), ("en", "English")))
    def test_functionary_role_admin_uses_local_language_tabs(self):
        self.assertTrue(issubclass(FunctionaryRoleAdmin, LanguageTabbedTranslationAdmin))

        model_admin = admin.site._registry[FunctionaryRole]
        form = model_admin.get_form(RequestFactory().get('/admin/functionaries/functionaryrole/add/'))

        self.assertIn('title_sv', form.base_fields)
        self.assertIn('title_en', form.base_fields)
        self.assertNotIn('title_fi', form.base_fields)
        self.assertIn('js/admin_translation_tabs.js', str(model_admin.media))
        self.assertNotIn('ajax.googleapis.com/ajax/libs/jqueryui', str(model_admin.media))
        self.assertEqual(model_admin.translation_status(FunctionaryRole(title_sv='Chair')), 'sv: 1/1; en: 0/1')

    def test_admin_media_paths_resolve_in_the_static_layout(self):
        """Admin Media paths must match the collected static layout.

        STATICFILES_DIRS collects static/common contents without the common/
        prefix (static/common/js/admin_translation_tabs.js is served as
        js/admin_translation_tabs.js), and every template references common
        assets unprefixed. A common/... Media reference (or a missing file)
        makes the manifest lookup fail and 500s every admin page using that
        Media class (2026-08-30).
        """
        common_static = Path(settings.BASE_DIR) / 'static/common'

        for admin_class in (LanguageTabbedTranslationAdmin, PDFFileAdmin):
            media = admin_class.Media
            paths = [*getattr(media, 'js', ())]
            for group in getattr(media, 'css', {}).values():
                paths.extend(group)
            self.assertTrue(paths, f'{admin_class.__name__}.Media declares no paths')
            for path in paths:
                self.assertFalse(
                    path.startswith('common/'),
                    f'{admin_class.__name__}.Media references {path} with the '
                    'common/ prefix, which the static layout strips',
                )
                self.assertTrue(
                    (common_static / path).is_file(),
                    f'{admin_class.__name__}.Media references {path}, which does not exist under {common_static}',
                )

    @override_settings(ENABLE_LANGUAGE_FEATURES=False)
    def test_translation_coverage_is_hidden_when_language_features_are_disabled(self):
        model_admin = admin.site._registry[FunctionaryRole]
        self.assertNotIn('translation_status', model_admin.get_list_display(RequestFactory().get('/admin/')))

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
