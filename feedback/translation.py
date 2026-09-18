from modeltranslation.translator import TranslationOptions, register

from core.modeltranslation import get_translation_languages
from feedback.models import FeedbackFormSettings

TRANSLATION_LANGUAGES = get_translation_languages()


@register(FeedbackFormSettings)
class FeedbackFormSettingsTranslationOptions(TranslationOptions):
    fields = ('intro_text',)
    languages = TRANSLATION_LANGUAGES
