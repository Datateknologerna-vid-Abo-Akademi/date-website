"""Find the shared inline-SVG icon for a footer social button, if there is one."""

import re

from django import template
from django.template import TemplateDoesNotExist
from django.template.loader import get_template

register = template.Library()

# Only plain lowercase identifiers of at most 64 characters can name an icon
# file, so a SOCIAL_BUTTONS value can never point the lookup outside
# core/svg/social/ or exceed the filesystem's per-name length limit.
_ICON_NAME = re.compile(r'[a-z0-9-]{1,64}')


@register.simple_tag
def social_icon_template(name):
    """Return the template path of the shared SVG icon for ``name``, or ``''``.

    The footer renders ``core/svg/social/<name>.svg`` for a ``SOCIAL_BUTTONS``
    entry when that template exists, and falls back to the Line Awesome
    icon-font class ``fab <name>`` when it doesn't. A platform Line Awesome
    lacks therefore needs only one SVG file in ``templates/common/core/svg/social/``
    to be usable by every association; an association can replace a single
    icon by putting a file at the same path in its own template directory.
    """
    if not isinstance(name, str) or not _ICON_NAME.fullmatch(name):
        return ''
    template_name = f'core/svg/social/{name}.svg'
    try:
        get_template(template_name)
    except TemplateDoesNotExist, OSError:
        # An unreadable or missing icon file falls back to the icon font, so a
        # broken icon never breaks the footer.
        return ''
    return template_name
