"""Template tag for the lunchmenu.fi student lunch widget."""

from django import template
from django.conf import settings

from date.lunch import student_lunch_link, widget_language

register = template.Library()


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
    attributes.append(('data-lang', widget_language()))
    attributes.append(('data-count', str(count)))
    attributes.append(('data-heading', str(heading)))
    attributes.append(('data-accent', settings.LUNCH_ACCENT))
    return attributes


@register.inclusion_tag('date/components/lunch_widget.html')
def lunch_widget(count=None, heading=3, wrapper_class='lunch-container'):
    """Render the official lunchmenu.fi student lunch widget.

    Returns no markup when ``LUNCH_ENABLED`` is off. The box carries a link to
    its city's lunch list, which the embed shows until it draws the widget and
    keeps where scripts can't run.
    """
    if not settings.LUNCH_ENABLED:
        return {'enabled': False}

    fallback_url, fallback_text = student_lunch_link()
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
