from modeltranslation.translator import register, TranslationOptions
from staticpages.models import StaticPage, StaticPageNav, StaticUrl


@register(StaticPage)
class StaticPageTranslationOptions(TranslationOptions):
    fields = ('title', 'content',)
    languages = ('sv', 'en', 'fi')


@register(StaticPageNav)
class StaticPageNavTranslationOptions(TranslationOptions):
    fields = ('category_name',)
    languages = ('sv', 'en', 'fi')


@register(StaticUrl)
class StaticUrlTranslationOptions(TranslationOptions):
    fields = ('title',)
    languages = ('sv', 'en', 'fi')
