from django import template
from django.template.defaultfilters import stringfilter
import re

from pages.models.epd import Unit

register = template.Library()


@register.filter(is_safe=True)
@stringfilter
def superscript_units(value):
    return re.sub(r"\^(\d+)", r"<sup>\1</sup>", value)


@register.filter(is_safe=True)
@stringfilter
def strip(value):
    return value.strip()


@register.filter(is_safe=True)
def get_step(selection_unit):
    if selection_unit in [Unit.PCS]:
        return "1"
    return "0.01"
