from django import template
from django.template.defaultfilters import stringfilter
import re
from decimal import Decimal, ROUND_HALF_UP

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

@register.filter(is_safe=True)
def get_item(dictionary, key):
    return dictionary.get(key)


_UNIT_DISPLAY = {
    "kwh": "kWh",
    "m3": "m³",
    "m2": "m²",
    "kg": "kg",
    "m": "m",
    "pcs": "pcs",
    "l": "L",
}

@register.filter(is_safe=True)
@stringfilter
def display_unit(value):
    return _UNIT_DISPLAY.get(value, value)


_UNIT_DISPLAY_OP = {
    "kwh": "kWh/yr",
    "m3": "m³/yr",
    "kg": "kg/yr",
    "liter": "liter/yr",
    "l": "liter/yr",
}

@register.filter(is_safe=True)
@stringfilter
def display_unit_op(value):
    return _UNIT_DISPLAY_OP.get(value, value)


# Construction-phase energy (A5.2) is a one-off total for the whole build, not
# a yearly rate, so the "/yr" that display_unit_op appends is wrong there -
# 2,000 litres of site diesel is not 2,000 litres a year.
_UNIT_DISPLAY_CONSTR = {
    "kwh": "kWh",
    "mj": "MJ",
    "m3": "m\u00b3",
    "kg": "kg",
    "ton": "tonnes",
    "liter": "litres",
    "l": "litres",
}


@register.filter(is_safe=True)
@stringfilter
def display_unit_constr(value):
    return _UNIT_DISPLAY_CONSTR.get(value, value)



@register.filter
def has_gcca_image(label):
    """True when a GCCA band has a label image on disk.

    The band is read from the database and interpolated straight into a static
    path, so a score the image set no longer covers renders a dead link.

    This is not hypothetical. The scale was corrected from A-G to the published
    AA-F and GCCA_label_G.svg was deleted with it, but any database not yet
    re-rated by `apply_gcca_concrete_labels --overwrite` still holds "G" rows -
    which is exactly the state after a deploy where that command has not been
    run. Every concrete still labelled "G" would show a broken image in the
    material picker.

    Checked rather than assumed: whitenoise's CompressedManifestStaticFilesStorage
    returns the plain URL for a file missing from the manifest instead of
    raising, so this is a broken image and not a 500.
    """
    from pages.scripts.Label_mapping.gcca_rating import GCCA_BANDS
    return label in GCCA_BANDS
