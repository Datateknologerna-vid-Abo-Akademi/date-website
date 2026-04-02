from modeltranslation.translator import register, TranslationOptions
from news.models import Post, Category


@register(Post)
class PostTranslationOptions(TranslationOptions):
    fields = ('title', 'content',)
    languages = ('sv', 'en', 'fi')


@register(Category)
class CategoryTranslationOptions(TranslationOptions):
    fields = ('name',)
    languages = ('sv', 'en', 'fi')
