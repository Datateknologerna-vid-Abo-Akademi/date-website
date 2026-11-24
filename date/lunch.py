"""Shared lunchmenu.fi links and language selection."""

from django.conf import settings
from django.utils.translation import get_language, gettext

WIDGET_LANGUAGES = ('fi', 'sv', 'en')
SITE_URL = 'https://lunchmenu.fi/'

# The city slug differs by language. Each entry is the path to today's
# student lunch list and the label used by lunchmenu.fi's embed.
CITY_PAGES = {
    'turku': {
        'fi': ('lounaslistat/turku/tanaan', 'Lounas Turku'),
        'sv': ('sv/lunchlistor/abo/idag', 'Lunch i Åbo'),
        'en': ('en/lunch-lists/turku/today', 'Lunch in Turku'),
    },
}


def widget_language():
    """Return the active language if supported by the widget, otherwise Swedish."""
    language = (get_language() or '').split('-')[0].lower()
    return language if language in WIDGET_LANGUAGES else 'sv'


def student_lunch_link():
    """Return the student lunch URL and label for the configured city and active language."""
    slug = str(settings.LUNCH_CITY).strip().lower()
    page = CITY_PAGES.get(slug, {}).get(widget_language())
    if page is None:
        return SITE_URL, gettext('Lunch')
    path, label = page
    return SITE_URL + path, label
