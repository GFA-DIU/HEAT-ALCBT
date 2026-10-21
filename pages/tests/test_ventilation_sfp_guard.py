"""A ventilation efficiency in the wrong unit, and the 4.3 GWh it produced.

"Baseline efficiency" on the ventilation sheets is Specific Fan Power in
W/CMH. The form asks for 0.30-1.20 and caps the field at 10. The column header
said only "Baseline efficiency", with no unit, so it reads like a percentage -
and the importer applied no bound at all.
"""
import warnings

import openpyxl
import pytest

from pages.views.building.import_building import (
    MAX_SPECIFIC_FAN_POWER_W_PER_CMH, _calc_vent_power,
)

TEMPLATE = "static/docs/import-template.xlsx"


@pytest.mark.parametrize("sfp", [0.30, 0.75, 1.20, 2.5, 10])
def test_a_plausible_fan_power_still_computes(sfp):
    assert _calc_vent_power(6000, sfp, 4) is not None


def test_the_value_that_produced_four_million_kwh_is_refused():
    """6,000 CMH x 75 W/CMH x 4 units = 1,800 kW, which came out as
    4,322,970 kWh/yr from one AHU row and pushed the building's operational
    baseline to 1,495 kgCO2eq/m2/yr - about ten times a real office."""
    assert _calc_vent_power(6000, 75, 4) is None


def test_the_guard_matches_the_forms_own_cap():
    """The form's field is max="10". The importer must not be looser than the
    screen it mirrors."""
    assert MAX_SPECIFIC_FAN_POWER_W_PER_CMH == 10.0
    assert _calc_vent_power(6000, 10.0, 4) is not None
    assert _calc_vent_power(6000, 10.1, 4) is None


def test_a_sensible_row_gives_a_sensible_figure():
    """4 units, 6,000 CMH, 0.75 W/CMH = 18 kW, not 1,800."""
    assert _calc_vent_power(6000, 0.75, 4) == 18.0


@pytest.mark.parametrize("bad", [0, -1, None, "", "abc"])
def test_rubbish_still_returns_none(bad):
    assert _calc_vent_power(6000, bad, 4) is None


def test_the_template_names_the_unit():
    """The unlabelled header is what made the wrong value look right - the
    same omission as the hot water efficiency column."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        wb = openpyxl.load_workbook(TEMPLATE, data_only=True)

    checked = 0
    for name in wb.sheetnames:
        if not name.startswith("Ventillation"):
            continue
        headers = [str(c.value or "").replace("\n", " ").strip()
                   for c in wb[name][1]]
        efficiency = [h for h in headers if h.startswith("Baseline efficiency")]
        assert efficiency, "%s has no efficiency column" % name
        assert "W/CMH" in efficiency[0], "%s: %r" % (name, efficiency[0])
        checked += 1
    assert checked == 5, "expected five ventilation sheets, saw %s" % checked
