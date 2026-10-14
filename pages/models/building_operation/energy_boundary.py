"""What a cooling record's electricity figure already covers.

BEAT adds every record once and deducts nothing, and nothing linked an indoor
unit to the outdoor unit serving it. That made two opposite errors possible on
the same building, neither visible:

  * a matched split system's total input entered against the outdoor unit, with
    the indoor fan also entered as a fan coil unit - the fan counted twice
  * a chilled-water FCU's fan omitted because the user assumed the chiller
    figure covered it

Both look identical in the database. The difference is not in the equipment but
in what the entered number already includes, which only the user knows. So BEAT
asks.

The field is deliberately three-valued. "Not specified" is the default and the
honest state for the 273 records entered before this existed: BEAT keeps adding
them exactly as it did, and no figure anyone has already seen changes.
"""
from django.db import models
from django.utils.translation import gettext_lazy as _


class EnergyBoundary(models.TextChoices):
    """Which equipment the entered electricity figure covers.

    COMPLETE_SYSTEM
        The figure covers the whole system including its indoor fans. This is
        the usual case for a matched split or packaged unit: BEAT derives the
        energy from cooling capacity divided by efficiency, and the
        manufacturer's capacity and COP/EER describe the matched pair.
        A fan linked to this record is already inside the figure, so BEAT must
        NOT add it again.

    EQUIPMENT_ONLY
        The figure covers the outdoor unit or the chiller alone. Daikin's VRV
        sheets label power consumption "outdoor unit", and a chiller's input is
        its own. Indoor fan electricity is genuinely separate and BEAT adds it.

    UNKNOWN
        Not stated. BEAT adds every record, which is what it did before this
        field existed. Chosen as the default precisely because it changes
        nothing.
    """

    UNKNOWN = "unknown", _("Not specified — fans are added separately")
    COMPLETE_SYSTEM = "complete_system", _("Complete system, including indoor fans")
    EQUIPMENT_ONLY = "equipment_only", _("Outdoor unit / chiller only")


#: Boundaries where a linked indoor fan's electricity is ALREADY inside the
#: parent's figure and must not be added again.
FANS_INCLUDED = (EnergyBoundary.COMPLETE_SYSTEM,)


def fan_is_already_counted(parent) -> bool:
    """True when this parent's figure already includes its indoor fans.

    Returns False for an unlinked fan and for a parent that has not said - the
    behaviour BEAT had before the link existed, so an unspecified record is
    never silently reduced.
    """
    if parent is None:
        return False
    return getattr(parent, "energy_boundary", None) in FANS_INCLUDED
