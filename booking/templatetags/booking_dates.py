"""Date formatting for the public booking lists."""

from django import template
from django.utils import timezone
from django.utils.formats import date_format

from .. import access

register = template.Library()


@register.filter
def short_date(value):
    """A booking date as "mån 4.10", with the year when it is not this one.

    The weekday matters because a room is booked for a reason and the board and
    the booker both think in weekdays, and the year matters because a date badge
    reading 4.10 is ambiguous once a booking is in another year. The month and
    weekday names come from the active locale, so this is the one place that
    formatting decision lives.
    """
    local = timezone.localtime(value)
    today = timezone.localtime(access.now_at())
    how = 'D j.n' if local.year == today.year else 'D j.n Y'
    return date_format(local, how)


@register.filter
def year_suffix(value):
    """A leading-space year for a date outside the current one, else nothing.

    The front page card shows the day and the month as separate elements, so it
    needs the year on its own rather than a whole formatted date.
    """
    local = timezone.localtime(value)
    today = timezone.localtime(access.now_at())
    return '' if local.year == today.year else f' {local.year}'
