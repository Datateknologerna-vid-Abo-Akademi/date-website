from modeltranslation.translator import TranslationOptions, register

from core.modeltranslation import get_translation_languages
from ctf.models import Ctf

TRANSLATION_LANGUAGES = get_translation_languages()


@register(Ctf)
class CtfTranslationOptions(TranslationOptions):
    fields = (
        'title',
        'content',
    )
    languages = TRANSLATION_LANGUAGES
