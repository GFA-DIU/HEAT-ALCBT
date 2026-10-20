"""The VRF tab of the import template never worked.

Found by parsing a VRF row laid out exactly as the shipped template lays it
out, rather than by reading the parser.
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
