"""Cooling tabs read one column out.

The VRF tab and both chiller tabs carry a leading "Type of cooling system"
column that Window and Split do not, and the shared parser used Window/Split
indices for all of them.

Found by parsing rows laid out exactly as the shipped template lays them out,
rather than by reading the parser.
"""
import pytest

from pages.views.building.import_building import _parse_cooling_rows


# static/docs/import-template.xlsx, "Cooling System - Variable refri", row 1.
# The leading "Type of cooling system" column is the one Window and Split
# do not have.
VRF_ROW = ["VRF", 2019, "R-410A", 6.5, 45.0, "kW", 3, 10, 10, 6, 50, 12.5,
           3.60, "B", 4, ""]

EXPECTED = {
    "year_of_installation": "2019",
    "type_of_refrigerants": "R-410A",
    "refrigerant_quantity": "6.5",
    "cooling_capacity_per_unit": "45.0",
    "cooling_capacity_unit": "kw",
    "number_of_units": "3",
    "hours_per_day": "10",
    "days_per_week": "6",
    "weeks_per_year": "50",
    "power_input_per_unit": "12.5",
    "eer_iseer_cop": "3.6",
    "energy_efficiency_label": "B",
    "number_of_stars": "4",
}


@pytest.mark.parametrize("field,expected", sorted(EXPECTED.items()))
def test_every_vrf_field_lands_in_its_own_column(field, expected):
    """Every one of these was one place to the left: the year read "VRF", the
    refrigerant quantity read "R-410A", the unit count read "kW" and the
    efficiency read the power input."""
    row = _parse_cooling_rows("vrf", [VRF_ROW])[0]
    assert str(row[field]) == expected


def test_vrf_energy_ties_out():
    """3 units x 12.5 kW x 10 h x 6 d x 50 wk = 112,500 kWh/yr. Before the
    offset this came out blank, because the shifted values did not parse."""
    row = _parse_cooling_rows("vrf", [VRF_ROW])[0]
    assert row["total_energy_consumption_annually"] == "112500.000"


def test_the_offset_is_not_applied_to_split():
    """Window and Split have no leading column, so they must be untouched."""
    split = ["2018", "R-410A", 1.8, 5.0, "kW", 24, 6, 10, 6, 50, 1.55, 3.30,
             "A", 5, ""]
    row = _parse_cooling_rows("split ac", [split])[0]
    assert row["year_of_installation"] == "2018"
    assert row["eer_iseer_cop"] == "3.3"
    assert row["number_of_units"] == "24"


def test_the_offset_is_not_applied_to_packaged():
    """PackagedDuctable has the extra column too, but its own branch already
    uses absolute indices - applying the offset there would break it."""
    packaged = ["Rooftop", "2020", "R-410A", 3.2, 28.0, "kW", 2, 8, 10, 6, 50,
                8.4, 3.40, "", "A", 4, ""]
    row = _parse_cooling_rows("packagedductab", [packaged])[0]
    assert row["year_of_installation"] == "2020"
    assert row["eer_iseer_cop"] == "3.4"


# --- the chillers ----------------------------------------------------------
#
# Worse than VRF, because these still produced a figure. VRF rows failed on a
# year of "VRF"; a chiller row reported 4,320,000 kWh/yr.

WATER_COOLED_ROW = ["Water cooled chiller", 2017, "R-134a", 120, 400, 2, 10,
                    12, 6, 50, 0.62, "Yes", "No", 6.4, 0.85, 250, 5.6, "A", 4, ""]

WATER_COOLED_EXPECTED = {
    "year_of_installation": "2017",
    "type_of_refrigerants": "R-134a",
    "refrigerant_quantity": "120",
    "total_cooling_load": "400",
    "number_of_chillers": "2",
    "baseline_leakage_factor": "10",
    "annual_operating_hours_per_day": "12",
    "annual_operating_days_per_week": "6",
    "annual_operating_weeks_per_year": "50",
    "baseline_cooling_efficiency": "0.62",
    "cop": "5.6",
    "number_of_stars": "4",
}

# air-cooled puts IPLV at 13, system power at 14 and COP at 15, one fewer than
# water-cooled, which has a cooling load factor at 14.
AIR_COOLED_ROW = ["Air cooled chiller", 2016, "R-410A", 90, 300, 3, 10, 10, 6,
                  52, 0.85, "No", "No", 5.1, 210, 3.9, "B", 3, ""]

AIR_COOLED_EXPECTED = {
    "year_of_installation": "2016",
    "total_cooling_load": "300",
    "number_of_chillers": "3",
    "baseline_cooling_efficiency": "0.85",
    "cop": "3.9",
    "number_of_stars": "3",
}


@pytest.mark.parametrize("field,expected", sorted(WATER_COOLED_EXPECTED.items()))
def test_water_cooled_fields_land_in_their_own_columns(field, expected):
    row = _parse_cooling_rows("water cooled", [WATER_COOLED_ROW])[0]
    assert str(row[field]) == expected


@pytest.mark.parametrize("field,expected", sorted(AIR_COOLED_EXPECTED.items()))
def test_air_cooled_fields_land_in_their_own_columns(field, expected):
    row = _parse_cooling_rows("air cooled", [AIR_COOLED_ROW])[0]
    assert str(row[field]) == expected


def test_the_chiller_energy_that_was_nearly_five_times_too_high():
    """400 RT x 0.62 kW/RT x 12 h x 6 d x 50 wk = 892,800 kWh/yr. Shifted, it
    read the load as 120 and the efficiency as 50 kW/RT and reported
    4,320,000 - a plausible figure for a large plant."""
    row = _parse_cooling_rows("water cooled", [WATER_COOLED_ROW])[0]
    energy = float(row["total_energy_consumption_of_chiller_system_annually"])
    assert abs(energy - 892800) < 1


def test_the_chiller_row_validates():
    from pages.forms.cooling_system_form import CoolingSystemChillerForm

    row = _parse_cooling_rows("air cooled", [AIR_COOLED_ROW])[0]
    assert CoolingSystemChillerForm(data=row).is_valid()


def test_the_offset_covers_exactly_the_tabs_that_need_it():
    from pages.views.building.import_building import _TABS_WITH_LEADING_COLUMN

    assert _TABS_WITH_LEADING_COLUMN == {"vrf", "water cooled", "air cooled"}
    # PackagedDuctable has the leading column but its own absolute indices.
    assert "packagedductab" not in _TABS_WITH_LEADING_COLUMN
