from modeltranslation.translator import register, TranslationOptions
from events.models import Event, EventAttendees, EventRegistrationForm


@register(Event)
class EventTranslationOptions(TranslationOptions):
    fields = ('title', 'content',)
    languages = ('sv', 'en', 'fi')


@register(EventAttendees)
class EventAttendeesTranslationOptions(TranslationOptions):
    fields = ()
    languages = ('sv', 'en', 'fi')


@register(EventRegistrationForm)
class EventRegistrationFormTranslationOptions(TranslationOptions):
    fields = ()
    languages = ('sv', 'en', 'fi')
