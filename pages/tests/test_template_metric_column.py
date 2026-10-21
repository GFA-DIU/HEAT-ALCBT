"""The efficiency-metric column, in the shipped template and in the parser.

The parser learned to read this column before the template had it, so every
imported air conditioner was still read as COP. These tests tie the two
together: if the column ever moves, or the parser's index changes, one of them
fails.
"""
import warnings

import openpyxl
import pytest

from pages.views.building.import_building import _parse_cooling_rows

TEMPLATE = "static/docs/import-template.xlsx"

# sheet -> the 0-based column the parser reads the metric from.
# VRF is 16 rather than 15 because that tab carries a leading
# "Type of cooling system" column the others do not.
METRIC_COLUMN = {
    "Cooling System - Window air con": 15,
    "Cooling System - Split air cond": 15,
    "Cooling System - Variable refri": 16,
    "Cooling System - PackagedDuctab": 17,
}


@pytest.mark.parametrize("sheet,col", sorted(METRIC_COLUMN.items()))
def test_the_shipped_template_has_the_column(sheet, col):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        wb = openpyxl.load_workbook(TEMPLATE, data_only=True)
    header = wb[sheet].cell(row=1, column=col + 1).value
    assert header and "Efficiency metric" in str(header)


def test_the_template_still_carries_its_dropdowns():
    """openpyxl cannot round-trip this file - saving through it destroys the
    x14 extension validations. The column was added by editing the XML in
    place for that reason, and this fails if anyone saves it the easy way."""
    import re
    import zipfile

    z = zipfile.ZipFile(TEMPLATE)
    x14 = sum(
        len(re.findall(r"<x14:dataValidation[ >]", z.read(n).decode("utf-8", "ignore")))
        for n in z.namelist() if n.endswith(".xml")
    )
    assert x14 == 30, f"expected 30 x14 validations, found {x14}"


@pytest.mark.parametrize("text,expected", [
    ("EER", "eer"), ("ISEER", "iseer"), ("CSPF", "cspf"),
    ("EER (W/W)", "eer_ww"), ("", "cop"),
])
def test_a_split_row_carries_its_metric_through(text, expected):
    row = ["2018", "R-32", 1.2, 5.0, "kW", 2, 6, 10, 6, 50, 1.5, 11.60,
           "", "", "", text]
    parsed = _parse_cooling_rows("split ac", [row])[0]
    assert parsed["efficiency_metric"] == expected


def test_a_vrf_row_carries_its_metric_through():
    """One past VRF's own energy column, because of the leading column."""
    row = ["VRF", 2019, "R-410A", 6.5, 45.0, "kW", 3, 10, 10, 6, 50, 12.5,
           3.60, "B", 4, "", "ISEER"]
    parsed = _parse_cooling_rows("vrf", [row])[0]
    assert parsed["efficiency_metric"] == "iseer"
    assert parsed["eer_iseer_cop"] == "3.6"


def test_the_thai_case_end_to_end():
    """Thailand's EGAT No.5 threshold is EER >= 11.60 in Btu/h per watt.
    Stored as COP that machine looks 3.4x more efficient than it is."""
    row = ["2018", "R-32", 1.2, 5.0, "kW", 2, 6, 10, 6, 50, 1.5, 11.60,
           "", "", "", "EER"]
    assert _parse_cooling_rows("split ac", [row])[0]["efficiency_metric"] == "eer"
