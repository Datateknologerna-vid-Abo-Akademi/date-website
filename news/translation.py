from modeltranslation.translator import register, TranslationOptions
from core.modeltranslation import get_translation_languages
from news.models import Post, Category

TRANSLATION_LANGUAGES = get_translation_languages()


@register(Post)
class PostTranslationOptions(TranslationOptions):
    fields = ('title', 'content',)
    languages = TRANSLATION_LANGUAGES


@register(Category)
class CategoryTranslationOptions(TranslationOptions):
    fields = ('name',)
    languages = TRANSLATION_LANGUAGES
