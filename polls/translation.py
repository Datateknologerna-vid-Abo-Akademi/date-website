from modeltranslation.translator import TranslationOptions, register

from core.modeltranslation import get_translation_languages
from polls.models import Choice, Question

TRANSLATION_LANGUAGES = get_translation_languages()


@register(Question)
class QuestionTranslationOptions(TranslationOptions):
    fields = ("question_text",)
    languages = TRANSLATION_LANGUAGES


@register(Choice)
class ChoiceTranslationOptions(TranslationOptions):
    fields = ("choice_text",)
    languages = TRANSLATION_LANGUAGES
