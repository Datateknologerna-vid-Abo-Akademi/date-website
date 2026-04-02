from django import template
from django.utils.translation import get_language

from date.language_utils import localize_url

register = template.Library()


@register.filter
def localized_url(url):
    return localize_url(url, get_language())
