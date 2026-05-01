from modeltranslation.translator import register, TranslationOptions
from core.modeltranslation import get_translation_languages
from events.models import Event, EventAttendees, EventRegistrationForm

TRANSLATION_LANGUAGES = get_translation_languages()


@register(Event)
class EventTranslationOptions(TranslationOptions):
    fields = ('title', 'content',)
    languages = TRANSLATION_LANGUAGES


@register(EventAttendees)
class EventAttendeesTranslationOptions(TranslationOptions):
    fields = ()
    languages = TRANSLATION_LANGUAGES


@register(EventRegistrationForm)
class EventRegistrationFormTranslationOptions(TranslationOptions):
    fields = ()
    languages = TRANSLATION_LANGUAGES
