"""Reading EPD figures out of an ILCD dataset.

The dangerous case here is the declared amount. A steel dataset states a
reference flow of 1 whose flow property meanValue is 1000: one tonne. Reading
only the exchange gives 1 kg, and the EPD's 2,367 kgCO2e then reads as
2,367 kgCO2e per kilogram of steel, which is about a thousand times the real
figure and imports perfectly cleanly.

That is not a hypothetical. It happened on the first run over the 2026 Indian
batch and was caught only by the importer's plausibility band.
"""
import xml.etree.ElementTree as ET

from pages.management.commands.extract_environdec_ilcd import (
    gwp_modules, parse_unit)


# --- the functional unit, where one is stated ------------------------------

def test_a_stated_functional_unit_is_read():
    assert parse_unit("1 m2 of installed plasterboard of 12.5 mm") == ((1.0, "m2"), None)


def test_tonnes_normalise_to_ton():
    assert parse_unit("1 tonne of cement")[0] == (1.0, "ton")


def test_a_decimal_amount_is_kept():
    assert parse_unit("2.5 kg of paint")[0] == (2.5, "kg")


def test_an_unknown_unit_is_refused_not_guessed():
    parsed, why = parse_unit("1 Wp of a photovoltaic module")
    assert parsed is None
    assert "unrecognised declared unit" in why


def test_an_empty_functional_unit_is_refused():
    parsed, why = parse_unit("")
    assert parsed is None
    assert why


def test_a_product_name_in_the_unit_slot_is_refused():
    """Several datasets put the product name where the functional unit
    belongs. That must refuse, not return a number scraped out of the name."""
    parsed, _ = parse_unit("Magnetron coated glass on SGG PARSOL 6 mm")
    assert parsed is None


def test_a_zero_amount_is_refused():
    parsed, why = parse_unit("0 kg of nothing")
    assert parsed is None
    assert "declared amount" in why


# --- the GWP result --------------------------------------------------------

GWP_XML = """<process xmlns="http://lca.jrc.it/ILCD/Process"
    xmlns:common="http://lca.jrc.it/ILCD/Common"
    xmlns:epd="http://www.iai.kit.edu/EPD/2013">
  <LCIAResults>
    <LCIAResult>
      <referenceToLCIAMethodDataSet>
        <common:shortDescription>Acidification potential (AP)</common:shortDescription>
      </referenceToLCIAMethodDataSet>
      <common:other><epd:amount epd:module="A1-A3">9.99</epd:amount></common:other>
    </LCIAResult>
    <LCIAResult>
      <referenceToLCIAMethodDataSet>
        <common:shortDescription>Global Warming Potential - total (GWP-total)</common:shortDescription>
      </referenceToLCIAMethodDataSet>
      <common:other>
        <epd:amount epd:module="A1-A3">1.144</epd:amount>
        <epd:amount epd:module="A4">0.307</epd:amount>
        <epd:amount epd:module="C2">0.048</epd:amount>
      </common:other>
    </LCIAResult>
  </LCIAResults>
</process>"""


def test_the_gwp_total_result_is_the_one_read():
    """Acidification is listed first and carries an A1-A3 too. Taking the
    first result would report an acidification figure as carbon."""
    mods = gwp_modules(ET.fromstring(GWP_XML))
    assert mods["A1-A3"] == 1.144
    assert 9.99 not in mods.values()


def test_other_modules_come_through():
    mods = gwp_modules(ET.fromstring(GWP_XML))
    assert mods["A4"] == 0.307
    assert mods["C2"] == 0.048


def test_a_dataset_with_no_gwp_result_returns_nothing():
    xml = GWP_XML.replace("Global Warming Potential - total (GWP-total)",
                          "Ozone depletion (ODP)")
    assert gwp_modules(ET.fromstring(xml)) == {}
