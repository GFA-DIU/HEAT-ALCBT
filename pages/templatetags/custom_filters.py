from django import template
from django.template.defaultfilters import stringfilter
import re

register = template.Library()

@register.filter(is_safe=True)
@stringfilter
def superscript_units(value):
    return re.sub(r'\^(\d+)', r'<sup>\1</sup>', value)