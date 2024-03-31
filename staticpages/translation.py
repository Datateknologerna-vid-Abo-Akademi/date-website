from modeltranslation.translator import register, TranslationOptions
from staticpages.models import StaticPageNav, StaticUrl


@register(StaticPageNav)
class StaticPageNavTranslationOptions(TranslationOptions):
    fields = ('category_name',)
    languages = ('sv', 'en', 'fi')


@register(StaticUrl)
class StaticUrlTranslationOptions(TranslationOptions):
    fields = ('title',)
    languages = ('sv', 'en', 'fi')
