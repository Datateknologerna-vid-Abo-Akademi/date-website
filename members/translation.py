from modeltranslation.translator import register, TranslationOptions
from core.modeltranslation import get_translation_languages
from members.models import FunctionaryRole

TRANSLATION_LANGUAGES = get_translation_languages()


@register(FunctionaryRole)
class FunctionaryRoleTranslationOptions(TranslationOptions):
    fields = ('title',)
    languages = TRANSLATION_LANGUAGES