"""The lift estimate, which was computed in two places and disagreed.

The form pre-filled 69,189.15 while the summary showed 57,657.6 for the same
building. The tooltip, the hint text and the model all said the estimate is
7.5% of cooling, ventilation, lighting and hot water. Only the JavaScript
disagreed, and it was the number the user actually saw - and saved, after
which it counted as an entered figure and the estimate stopped applying.
"""
from decimal import Decimal
from pathlib import Path

from pages.models.building_operation.energy_summary import (
    LIFT_ESTIMATE_FRACTION, lift_estimate_kwh,
)

REPO = Path(__file__).resolve().parents[2]
LIFT_FORM = REPO / ("templates/pages/add-building/components/"
                    "operational-details/lift-escalator-system.html")


def test_the_estimate_reproduces_the_reported_building():
    """Cooling 218,400 + ventilation 262,080 + lighting 157,248 + hot water
    131,040 = 768,768. 7.5% of that is 57,657.6, which is what the summary
    showed. The form showed 69,189.15, which is 7.5% of the same four plus
    153,753.6 of plug and equipment load."""
    assert lift_estimate_kwh(218400, 262080, 157248, 131040) == Decimal("57657.600")


def test_plug_load_is_not_in_the_base():
    """The whole point of the bug: adding plug load inflates it by about 20%."""
    four = lift_estimate_kwh(218400, 262080, 157248, 131040)
    with_plug = (Decimal("768768") + Decimal("153753.6")) * LIFT_ESTIMATE_FRACTION
    assert with_plug > four
    assert round(float(with_plug), 2) == 69189.12


def test_a_missing_system_is_skipped_not_treated_as_zero_error():
    assert lift_estimate_kwh(100, None, None, None) == Decimal("7.500")
    assert lift_estimate_kwh(None, None, None, None) == Decimal("0.000")


def test_the_form_does_not_compute_its_own_estimate():
    """One quantity, one implementation. The form reads what the server sends."""
    js = LIFT_FORM.read_text(encoding="utf-8")
    assert "data.lift_estimate_kwh" in js
    assert "total_kwh * 0.075" not in js
    assert "total_kwh*0.075" not in js


def test_the_endpoint_supplies_the_estimate():
    src = (REPO / "pages/views/building/building_step_operational.py").read_text(
        encoding="utf-8")
    assert "lift_estimate_kwh" in src
    assert '"lift_estimate_kwh": estimate' in src


def test_the_fraction_is_named_once():
    """A bare 0.075 in a second file is how this diverged the first time."""
    assert LIFT_ESTIMATE_FRACTION == Decimal("0.075")
    js = LIFT_FORM.read_text(encoding="utf-8")
    assert "0.075" not in js


def test_the_screen_text_still_describes_the_four_systems():
    js = LIFT_FORM.read_text(encoding="utf-8")
    assert "7.5% of cooling, ventilation, lighting and hot water" in js
