from modeltranslation.translator import register, TranslationOptions
from polls.models import Question, Choice


@register(Question)
class QuestionTranslationOptions(TranslationOptions):
    fields = ('question_text',)
    languages = ('sv', 'en', 'fi')


@register(Choice)
class ChoiceTranslationOptions(TranslationOptions):
    fields = ('choice_text',)
    languages = ('sv', 'en', 'fi')
