from modeltranslation.translator import TranslationOptions, register

from core.modeltranslation import get_translation_languages
from functionaries.models import FunctionaryRole

TRANSLATION_LANGUAGES = get_translation_languages()


@register(FunctionaryRole)
class FunctionaryRoleTranslationOptions(TranslationOptions):
    fields = ('title',)
    languages = TRANSLATION_LANGUAGES
