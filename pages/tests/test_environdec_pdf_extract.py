"""The PDF extractor must read the right column, or refuse.

These are the three table layouts actually present in the EPD International
library for Cambodia, India, Indonesia, Vietnam and Thailand, transcribed from
real declarations. A GWP figure taken from the wrong column looks entirely
plausible and would silently become a building's embodied carbon, so the
refusal cases matter as much as the successes.
"""
from pages.scripts.environdec.pdf_extract import extract_from_text

# Jayaboard Sheetrock Protech 9mm (Indonesia) - wide table, point decimals,
# a B1-B7 column, and footnote markers on the header labels.
WIDE = """
ENVIRONMENTAL IMPACTS
Parameter Unit A1-3*** A4 A5 B1-B7 C1 C2 C3 C4 D**
GWP-total kg CO2 eq. 1.19E+00 4.62E-02 4.00E-01 0.00E+00 3.14E-03 3.82E-02 0.00E+00 2.52E-01 0.00E+00
GWP-fossil kg CO2 eq. 1.71E+00 4.43E-02 3.38E-01 0.00E+00 3.01E-03 3.66E-02 0.00E+00 7.54E-02 0.00E+00
The declared unit is 1 m2 of plasterboard.
"""

# Keraflex Easy S1 (India) - comma decimals, no B column.
COMMA = """
A1-A3 A4 A5 C1 C2 C3 C4 D
GWP-total [kg CO2 eq.] 4,93E-01 6,26E-02 2,55E-03 5,27E-03 8,78E-03 2,93E-05 2,47E-02 -3,04E-04
The declared unit of 1 kg of product in 24 kg plastic bags.
"""

# Rajawali PPC (Indonesia) - vertical table, "6.00*102" for 6.00 x 10^2.
VERTICAL = """
Table 4. Mandatory impact category indicators according to EN 15804
Indicator Unit A1-A3
GWP-fossil kg CO2 eq. 6.00*102
GWP-biogenic* kg CO2 eq. 4.98*10-1
GWP-luluc kg CO2 eq. 2.57*10-1
GWP-total kg CO2 eq. 6.00*102
"""

# SCG Portland cement (Thailand) - indicator spelled out, biogenic and land-use
# rows sitting directly under the headline figure.
SPELLED_OUT = """
Impact per 1,000 kg average
Indicator Unit Total A1-A3
Global Warming Potential, GHG kg CO2 eq. 7.89E+02 **
Global Warming Potential, total kg CO2 eq. 7.89E+02 *
Global Warming Potential, fossil fuels kg CO2 eq. 7.88E+02 *
Global Warming Potential, biogenic kg CO2 eq. 2.32E-01 *
Global Warming Potential, land use and land use change kg CO2 eq. 1.04E-01
"""


def test_wide_table_reads_the_a1a3_column():
    r = extract_from_text(WIDE)
    assert r["ok"]
    assert r["gwp_a1a3"] == 1.19
    assert r["modules"]["A4"] == 0.0462
    assert r["modules"]["A5"] == 0.4
    assert (r["declared_amount"], r["declared_unit"]) == (1.0, "m2")


def test_comma_decimals_are_not_read_as_thousands_separators():
    r = extract_from_text(COMMA)
    assert r["ok"]
    assert r["gwp_a1a3"] == 0.493
    assert r["modules"]["D"] == -0.000304


def test_vertical_table_and_times_ten_notation():
    r = extract_from_text(VERTICAL)
    assert r["ok"]
    assert r["gwp_a1a3"] == 600.0


def test_prefers_total_over_fossil_and_never_biogenic():
    """The biogenic row is 0.232 - picking it would understate cement 3000x."""
    r = extract_from_text(SPELLED_OUT)
    assert r["ok"]
    assert r["gwp_row"] == "GWP-total"
    assert r["gwp_a1a3"] == 789.0
    assert r["declared_amount"] == 1000.0
    assert r["declared_unit"] == "kg"


def test_refuses_when_the_header_does_not_line_up():
    """One module, eight values: the columns cannot be placed, so refuse."""
    r = extract_from_text(
        "Indicator Unit A1-A3\n"
        "GWP-total kg CO2 eq. 1.0 2.0 3.0 4.0 5.0 6.0 7.0 8.0\n")
    assert not r["ok"]
    assert "mismatch" in r["reason"]


def test_refuses_when_there_is_no_header_at_all():
    r = extract_from_text("GWP-total kg CO2 eq. 1.19E+00 4.62E-02 4.00E-01\n")
    assert not r["ok"]


def test_refuses_an_unreadable_document():
    assert not extract_from_text("")["ok"]


LEGEND = """
Parameter Unit A1-A3
GWP-GHG = Global Warming Potential total excl. biogenic carbon following IPCC AR5 methodology.
"""


def test_refuses_an_acronym_legend_that_reads_like_a_data_row():
    """AR5 ends in a digit, and "Potential total" reads as the headline row.

    This legend line produced 5.0 kgCO2e per tonne for a CEM III/A cement -
    about 1/70th of the real figure, and perfectly plausible-looking in a
    spreadsheet. A table row is numbers after its first value; a sentence
    keeps using words.
    """
    assert not extract_from_text(LEGEND)["ok"], "a prose legend was read as a value"
