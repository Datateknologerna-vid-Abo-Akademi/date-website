from django import template
import re
from django.utils import timezone
from django.utils.timesince import timeuntil
from django.utils.timesince import timesince
from django.utils.translation import get_language


register = template.Library()


_FINNISH_FUTURE_UNIT_FORMS = {
    "minuutti": "minuutin",
    "minuuttia": "minuutin",
    "tunti": "tunnin",
    "tuntia": "tunnin",
    "päivä": "päivän",
    "päivää": "päivän",
    "viikko": "viikon",
    "viikkoa": "viikon",
    "kuukausi": "kuukauden",
    "kuukautta": "kuukauden",
    "vuosi": "vuoden",
    "vuotta": "vuoden",
}


def _normalize_finnish_future_relative(relative):
    return re.sub(
        r"(\d+)\s+([^\s,]+)",
        lambda match: f"{match.group(1)} {_FINNISH_FUTURE_UNIT_FORMS.get(match.group(2), match.group(2))}",
        relative,
    )


@register.filter
def localized_timeuntil(value):
    if value is None or value <= timezone.now():
        return ""

    relative = timeuntil(value)
    language = (get_language() or "").split("-")[0]

    if language == "fi":
        relative = _normalize_finnish_future_relative(relative)
        return f"{relative} kuluttua"
    if language == "en":
        return f"in {relative}"
    return f"om {relative}"


@register.filter
def comma_if(value):
    if not value:
        return ""
    return f", {value}"


@register.filter
def localized_timesince_ago(value):
    relative = timesince(value)
    language = (get_language() or "").split("-")[0]

    if language == "fi":
        return f"{relative} sitten"
    if language == "en":
        return f"{relative} ago"
    return f"för {relative} sedan"


@register.filter
def localized_remaining_places(value):
    language = (get_language() or "").split("-")[0]

    if language == "fi":
        noun = "paikka" if value == 1 else "paikkaa"
        return f"{value} {noun} jäljellä!"
    if language == "en":
        noun = "spot" if value == 1 else "spots"
        return f"{value} {noun} left!"
    noun = "plats" if value == 1 else "platser"
    return f"Det finns {value} {noun} kvar!"
