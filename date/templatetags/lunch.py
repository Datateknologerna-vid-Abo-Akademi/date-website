"""Template tag for the lunchmenu.fi student lunch widget."""

from django import template
from django.conf import settings
from django.utils.translation import get_language, gettext

register = template.Library()

# Languages the widget accepts, with Swedish as the fallback for anything else.
WIDGET_LANGUAGES = ('fi', 'sv', 'en')
SITE_URL = 'https://lunchmenu.fi/'

# lunchmenu.fi names its city pages per language: fi and en use the Finnish
# slug and sv the Swedish one. Each entry is the path of the city's student
# lunch list for today and the label its own embed snippet uses, keyed by
# LUNCH_CITY. Add a city here before pointing LUNCH_CITY at it, otherwise the
# box's link falls back to the site root.
CITY_PAGES = {
    'turku': {
        'fi': ('lounaslistat/turku/tanaan', 'Lounas Turku'),
        'sv': ('sv/lunchlistor/abo/idag', 'Lunch i Åbo'),
        'en': ('en/lunch-lists/turku/today', 'Lunch in Turku'),
    },
}


def _widget_language():
    """Return the widget language for the active language, or Swedish."""
    language = (get_language() or '').split('-')[0].lower()
    return language if language in WIDGET_LANGUAGES else 'sv'


def _widget_attributes(count, heading):
    """Build the widget data attributes in the order the embed documents.

    Values are stringified here rather than in the template: Django would
    localize a float coordinate to ``60,45`` under the Swedish locale, and the
    widget expects a dot decimal separator.
    """
    attributes = []
    if settings.LUNCH_LAT is not None and settings.LUNCH_LNG is not None:
        attributes.append(('data-lat', str(settings.LUNCH_LAT)))
        attributes.append(('data-lng', str(settings.LUNCH_LNG)))
    else:
        attributes.append(('data-city', settings.LUNCH_CITY))
    attributes.append(('data-lang', _widget_language()))
    attributes.append(('data-count', str(count)))
    attributes.append(('data-heading', str(heading)))
    attributes.append(('data-accent', settings.LUNCH_ACCENT))
    return attributes


def _fallback_link():
    """Return the box's own link and label for the active language.

    The widget keeps the box's markup until it is drawn, so this link is what a
    visitor sees first and what stays when the script can't run. Its label is
    lunchmenu.fi's own wording for that page, not site copy, so it is not run
    through gettext.
    """
    slug = str(settings.LUNCH_CITY).strip().lower()
    page = CITY_PAGES.get(slug, {}).get(_widget_language())
    if page is None:
        return SITE_URL, gettext('Lunch')
    path, label = page
    return SITE_URL + path, label


@register.inclusion_tag('date/components/lunch_widget.html')
def lunch_widget(count=None, heading=3, wrapper_class='lunch-container'):
    """Render the official lunchmenu.fi student lunch widget.

    Returns no markup when ``LUNCH_ENABLED`` is off. The box carries a link to
    its city's lunch list, which the embed shows until it draws the widget and
    keeps where scripts can't run.
    """
    if not settings.LUNCH_ENABLED:
        return {'enabled': False}

    fallback_url, fallback_text = _fallback_link()
    return {
        'enabled': True,
        'wrapper_class': wrapper_class,
        'widget_attributes': _widget_attributes(
            settings.LUNCH_COUNT if count is None else count,
            heading,
        ),
        'fallback_url': fallback_url,
        'fallback_text': fallback_text,
    }
