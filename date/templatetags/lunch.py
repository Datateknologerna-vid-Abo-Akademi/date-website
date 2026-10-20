"""Template tag for the lunchmenu.fi student lunch widget."""

from django import template
from django.conf import settings
from django.urls import NoReverseMatch, reverse
from django.utils.translation import get_language

register = template.Library()

# Languages the widget accepts, with Swedish as the fallback for anything else.
WIDGET_LANGUAGES = ('fi', 'sv', 'en')
FALLBACK_URL = 'https://lunchmenu.fi/'


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


@register.inclusion_tag('date/components/lunch_widget.html')
def lunch_widget(count=None, heading=3, wrapper_class='lunch-container'):
    """Render the official lunchmenu.fi student lunch widget.

    Returns no markup when ``LUNCH_ENABLED`` is off. The fallback anchor points
    at the local lunch page where that route exists and at lunchmenu.fi
    otherwise, so the link still works on associations without the page.
    """
    if not settings.LUNCH_ENABLED:
        return {'enabled': False}

    try:
        fallback_url = reverse('lunch')
    except NoReverseMatch:
        fallback_url = FALLBACK_URL

    return {
        'enabled': True,
        'wrapper_class': wrapper_class,
        'widget_attributes': _widget_attributes(
            settings.LUNCH_COUNT if count is None else count,
            heading,
        ),
        'fallback_url': fallback_url,
    }
