"""Include a template without the trailing newline Django's tags leave behind."""

from django import template
from django.template.loader import render_to_string
from django.utils.safestring import mark_safe

register = template.Library()


@register.simple_tag(name='include_clean')
def include_clean(template_name, **kwargs):
    """Render ``template_name`` with no trailing whitespace.

    ``{% include %}`` appends a newline after the included template, which adds a
    stray blank line to the rendered page when the partial is included between
    two script tags.

    The output is produced by ``render_to_string``, so every variable in the
    partial has already been escaped by Django's own template engine; marking it
    safe only stops the *markup* from being escaped a second time, which is what
    ``{% include %}`` does implicitly anyway.
    """
    rendered = render_to_string(template_name, kwargs)
    return mark_safe(rendered.strip())  # noqa: S308 — output of Django's template engine
