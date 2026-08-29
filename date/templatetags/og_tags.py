import re

from django import template
from django.utils.html import strip_tags

register = template.Library()


@register.filter
def plaintext_truncate(value, arg=160):
    try:
        max_length = int(arg)
    except Exception:
        max_length = 160

    if not value:
        return ""

    text = strip_tags(value)
    text = re.sub(r"\s+", " ", text)
    text = text.strip()

    if len(text) > max_length:
        text = text[:max_length] + "..."

    return text
