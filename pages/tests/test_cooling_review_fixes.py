"""Three cooling bugs found in a source-and-datasheet review, and their fixes.

Each was verified in the code before being fixed, and each produced a wrong
number that a user could not see was wrong.
"""
import re
from pathlib import Path

import pytest

from pages.models.building_operation.air_conditioning import (
    DIMENSIONLESS_METRICS, SEASONAL_METRICS, EfficiencyMetric)


REPO = Path(__file__).resolve().parents[2]
COOLING_FORM = REPO / ("templates/pages/add-building/components/"
                       "operational-details/cooling-system.html")
VENT_FORM = REPO / ("templates/pages/add-building/components/"
                    "operational-details/ventilation-system.html")
IMPORTER = REPO / "pages/views/building/import_building.py"


# --- 1. the chiller import counted the plant once per machine ---------------

def test_the_chiller_import_does_not_multiply_by_the_machine_count():
    """total_cooling_load is the whole plant's load, as the form states.

    The importer multiplied it by the number of chillers while the form did
    not, so the same plant entered by hand and by import differed by that
    count: a 15-chiller plant imported at 945,000 kWh/yr against 63,000
    entered manually. Three of the four stored records carried the inflated
    figure, each off by exactly its chiller count.
    """
    src = IMPORTER.read_text(encoding="utf-8")
    line = next(l for l in src.splitlines()
                if "energy = load" in l and " * " in l)
    assert "units" not in line, line


def test_the_import_and_the_form_compute_the_same_chiller_energy():
    src_js = COOLING_FORM.read_text(encoding="utf-8")
    js = next(l for l in src_js.splitlines()
              if "load * eff * hrs * days * weeks" in l)
    src_py = IMPORTER.read_text(encoding="utf-8")
    # " * " excludes the docstring, which spells the formula with multiplication
    # signs rather than operators
    py = next(l for l in src_py.splitlines()
              if "energy = load" in l and " * " in l)
    # same factors, in the same order, on both routes
    def factors(text):
        return re.findall(r"\b(load|eff|hrs|days|weeks|units)\b", text)
    assert factors(js) == factors(py), (js, py)


# --- 2. the save routine divided ISEER; the calculation did not -------------

def test_only_btu_based_eer_is_converted_on_save():
    """ISEER is already W/W - India's BEE defines it as CSTL/CSEC.

    The save routine divided ISEER by 3.412 while the on-screen calculation
    left it alone, so a user entering 5.30 saw the right energy, had 1.55
    stored, and on reopening read 3.4x the energy.
    """
    src = COOLING_FORM.read_text(encoding="utf-8")
    save_line = next(l for l in src.splitlines()
                     if "_metric ===" in l and "_effVal" in l)
    assert "'iseer'" not in save_line, save_line
    assert "_metric === 'eer'" in save_line


def test_both_code_paths_agree_on_which_metric_converts():
    src = COOLING_FORM.read_text(encoding="utf-8")
    # "/ 3.412" is the conversion itself; plain "3.412" also appears in the
    # tooltip text explaining it. The guard may sit on the line above, so each
    # conversion is judged with its immediate context.
    lines = src.splitlines()
    idx = [i for i, l in enumerate(lines) if "/ 3.412" in l]
    assert idx, "expected the conversion to be guarded by the metric"
    for i in idx:
        context = chr(10).join(lines[max(0, i - 2):i + 1])
        assert "=== 'eer'" in context, context
        assert "'iseer'" not in context, context


# --- 3. FCU power lost precision -------------------------------------------

def test_fcu_power_keeps_enough_precision_for_a_small_unit():
    """A chilled-water FCU draws tens of watts.

    Daikin's FWMJCC2BV1 is 63 W. Rounded to two decimals that is 0.06 kW, and
    over 2,000 hours BEAT reported 120 kWh instead of 126 - 5% low on every
    small unit.
    """
    src = VENT_FORM.read_text(encoding="utf-8")
    line = next(l for l in src.splitlines() if "perUnit * units" in l)
    assert "toFixed(2)" not in line, line
    decimals = int(re.search(r"toFixed\((\d+)\)", line).group(1))
    assert decimals >= 4, line


def test_the_rounding_that_was_wrong_really_was_wrong():
    """Documents the arithmetic, so the threshold is not lowered casually."""
    watts, hours = 63, 2000
    exact = watts / 1000 * hours
    two_dp = round(watts / 1000, 2) * hours
    assert exact == pytest.approx(126.0)
    assert two_dp == pytest.approx(120.0)
    four_dp = round(watts / 1000, 4) * hours
    assert four_dp == pytest.approx(126.0)


# --- the efficiency metrics the ALCBT countries actually label --------------

def test_the_metrics_cover_the_labels_used_across_alcbt():
    values = {c.value for c in EfficiencyMetric}
    # Thailand EGAT No.5 publishes SEER; Indonesia and Vietnam publish CSPF;
    # India publishes ISEER. EER appears in both W/W and Btu/h per W.
    for metric in ("cop", "eer", "eer_ww", "iseer", "cspf", "seer"):
        assert metric in values, metric


def test_only_btu_eer_is_treated_as_needing_conversion():
    for metric in ("cop", "eer_ww", "iseer", "cspf", "seer"):
        assert metric in DIMENSIONLESS_METRICS, metric
    assert "eer" not in DIMENSIONLESS_METRICS


def test_seasonal_ratings_are_marked_as_such():
    """Converting units never turns a seasonal rating into a full-load COP."""
    for metric in ("iseer", "cspf", "seer"):
        assert metric in SEASONAL_METRICS, metric
    for metric in ("cop", "eer", "eer_ww"):
        assert metric not in SEASONAL_METRICS, metric


def test_the_labels_state_both_the_unit_and_the_basis():
    for choice in EfficiencyMetric:
        label = str(choice.label)
        assert "W/W" in label or "Btu/h" in label, label
        assert "full load" in label or "seasonal" in label, label


# --- the unsourced factors now say so --------------------------------------

@pytest.mark.parametrize("fragment", [
    "that threshold is a BEAT assumption",      # the 7-year leakage switch
])
def test_the_hardcoded_factors_declare_themselves(fragment):
    """0.80 for a VSD, 0.70 for heat recovery and the 7-year leakage switch
    are BEAT's numbers, not the equipment's. The form says so now."""
    assert fragment in COOLING_FORM.read_text(encoding="utf-8")


# --- the CDU / FCU boundary -------------------------------------------------

METHODOLOGY = REPO / "docs/operational_carbon_methodology.md"
VENT_FORM_TXT = VENT_FORM  # alias, for readability below
SUMMARY = REPO / "pages/models/building_operation/energy_summary.py"


def test_energy_summary_adds_cooling_and_ventilation_without_deduction():
    """The documented rule: every record is added once, nothing is deducted.

    This is what makes a chilled-water chiller plus its FCUs correct and a
    split AC plus its own indoor unit a double count - and why BEAT cannot
    tell them apart.
    """
    src = SUMMARY.read_text(encoding="utf-8")
    cooling = next(l for l in src.splitlines() if "self.cooling_kwh = " in l
                   and "+" in l)
    assert "ac_sum + ch_sum + cas_sum" in cooling, cooling
    # the cassettes are excluded from ventilation, so they cannot land in both
    assert "exclude(" in src and "CASSETTE_AC" in src


def test_cassette_rows_cannot_be_counted_in_both_lines():
    src = SUMMARY.read_text(encoding="utf-8")
    assert "other_vent_qs = VentilationSystem.objects.filter(building=b).exclude(" in src


def test_there_is_still_no_link_between_indoor_and_outdoor_equipment():
    """Guards the claim the documentation makes.

    If someone adds the link, this test fails - and the methodology section
    saying BEAT cannot detect a double count must be rewritten at the same
    time, rather than being left behind as a false statement.
    """
    from pages.models.building_operation.ventilation import VentilationSystem
    from pages.models.building_operation.air_conditioning import (
        CoolingSystemAirConditioner)
    vent_fields = {f.name for f in VentilationSystem._meta.get_fields()}
    ac_fields = {f.name for f in CoolingSystemAirConditioner._meta.get_fields()}
    assert not {f for f in vent_fields if "cooling" in f or "parent" in f}
    assert not {f for f in ac_fields if "indoor" in f or "parent" in f}


def test_the_fcu_form_warns_at_the_point_of_entry():
    """Documentation nobody reads while typing does not prevent the mistake."""
    html = VENT_FORM.read_text(encoding="utf-8")
    assert "Enter each unit of electricity once" in html
    assert "chilled-water units served by a chiller" in html
    assert "cannot detect the difference" in html


def test_the_cooling_form_says_what_its_figure_already_covers():
    html = COOLING_FORM.read_text(encoding="utf-8")
    assert "cover the WHOLE system, indoor fan included" in html
