"""Resolving an EPD's declared unit when the publisher renamed the property.

15 Indian declarations were refused because the reference flow property's
shortDescription had been overwritten with the PRODUCT name: "Steel Plate",
"Manhole Cover", "VDS(r) Fixed Partition". Keyed on that name nothing matched
and every one of them was dropped, including three Saint-Gobain glasses and
Jindal's steel plate and rebar.

The UUID underneath is a reference to a standard ILCD flow property and
cannot be rewritten, so it is tried first.

The dangerous detail these tests pin down: the Mass, Area and Volume UUIDs
differ only in two characters in the middle.

    Mass    93a60a56-a3c8-11da-a746-0800200b9a66
    Area    93a60a56-a3c8-19da-a746-0800200c9a66
    Volume  93a60a56-a3c8-22da-a746-0800200c9a66

Truncating them while investigating made all three look like one identifier
and very nearly produced a mapping that labelled a carpet tile declared per
square metre as declared per kilogram. The carbon figure would then have been
divided by the wrong dimension and come out roughly five times too high, with
nothing on screen to show for it.
"""
from pages.management.commands.extract_environdec_ilcd import (
    unit_for_flow_property)

MASS = "93a60a56-a3c8-11da-a746-0800200b9a66"
AREA = "93a60a56-a3c8-19da-a746-0800200c9a66"
VOLUME = "93a60a56-a3c8-22da-a746-0800200c9a66"
LENGTH = "838aaa23-0117-11db-92e3-0800200c9a66"
PIECES = "01846770-4cfe-4a25-8ad9-919d8d378345"


# --- the three near-identical UUIDs stay apart -----------------------------

def test_mass_area_and_volume_are_not_confused():
    assert unit_for_flow_property(MASS, "") == "kg"
    assert unit_for_flow_property(AREA, "") == "m2"
    assert unit_for_flow_property(VOLUME, "") == "m3"


def test_length_is_not_read_as_area():
    """The Saint-Gobain VDS products look like area products and are
    declared per metre. Reading metres as square metres would silently
    misstate every one of them."""
    assert unit_for_flow_property(LENGTH, "") == "m"


def test_pieces():
    assert unit_for_flow_property(PIECES, "") == "pcs"


# --- the renamed property, which is the whole point ------------------------

def test_a_property_renamed_to_the_product_still_resolves():
    assert unit_for_flow_property(MASS, "Steel Plate") == "kg"
    assert unit_for_flow_property(MASS, "Manhole Cover") == "kg"
    assert unit_for_flow_property(LENGTH, "VDS® Fixed Partition") == "m"


def test_the_uuid_wins_over_the_name():
    """If the two ever disagree the UUID is the one that cannot be edited."""
    assert unit_for_flow_property(AREA, "Mass") == "m2"


# --- the name route still works where the name is honest -------------------

def test_an_english_name_still_resolves_without_a_uuid():
    assert unit_for_flow_property("", "Area") == "m2"
    assert unit_for_flow_property("", "Mass") == "kg"


def test_the_german_names_resolve():
    """These datasets return the property name in the language it was
    registered in, and several resolve to the German originals."""
    assert unit_for_flow_property("", "Masse") == "kg"
    assert unit_for_flow_property("", "Länge") == "m"


def test_case_and_padding_do_not_matter():
    assert unit_for_flow_property("  " + MASS.upper() + " ", "") == "kg"
    assert unit_for_flow_property("", "  AREA  ") == "m2"


# --- and it still refuses rather than guessing -----------------------------

def test_an_unknown_property_refuses():
    assert unit_for_flow_property("", "Steel Plate") is None
    assert unit_for_flow_property("not-a-uuid", "Manhole Cover") is None


def test_nothing_at_all_refuses():
    assert unit_for_flow_property("", "") is None
    assert unit_for_flow_property(None, None) is None


def test_watt_peak_still_refuses():
    """Solar modules declare per Wp. BEAT has no such unit and must not
    invent one."""
    assert unit_for_flow_property(
        "fbf65cf6-8d65-ed11-9f5e-6045bd95222d",
        "1 Wp of Bi-55- (520-550 Wp) Glass to Glass Module") is None
