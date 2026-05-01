from modeltranslation.translator import register, TranslationOptions
from core.modeltranslation import get_translation_languages
from staticpages.models import StaticPage, StaticPageNav, StaticUrl

TRANSLATION_LANGUAGES = get_translation_languages()


@register(StaticPage)
class StaticPageTranslationOptions(TranslationOptions):
    fields = ('title', 'content',)
    languages = TRANSLATION_LANGUAGES


@register(StaticPageNav)
class StaticPageNavTranslationOptions(TranslationOptions):
    fields = ('category_name',)
    languages = TRANSLATION_LANGUAGES


@register(StaticUrl)
class StaticUrlTranslationOptions(TranslationOptions):
    fields = ('title',)
    languages = TRANSLATION_LANGUAGES
