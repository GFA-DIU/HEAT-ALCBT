"""BoQ import: the density that turns a quantity into a carbon figure.

Density converts a BoQ quantity to mass and mass drives embodied carbon, so a
wrong density is a wrong carbon number rather than a visible error. The
importer had 444 lines and no tests at all.

Every case here failed before 20.10.2026.
"""
import pytest

from pages.views.building.import_boq import (
    _STD_VOLUME_DENSITY, _std_volume_density, autofix_conversions,
)


# --- the four that were wrong ----------------------------------------------

@pytest.mark.parametrize("name,expected,was,why", [
    ("Autoclaved Aerated Concrete block", 600, 2400,
     "matched 'concrete' before 'autoclaved aerated' - four times too heavy"),
    ("AAC block", 600, 600, "this one happened to work"),
    ("Lightweight concrete", 600, 2400, "same ordering fault"),
    ("Reinforced concrete", 2500, 7850,
     "matched 'reinforc' and took steel's density - 3.1x too heavy"),
    ("Glass wool insulation", 100, 2500,
     "matched 'glass' and took solid glass - the catalogue's own figure is 16"),
])
def test_specific_materials_beat_the_general_rule(name, expected, was, why):
    assert _std_volume_density(name) == expected, why


# --- the ordering is the fix, so the ordering is the test ------------------

def test_a_specific_rule_always_precedes_the_general_one_it_specialises():
    """The fix is the order, so moving "concrete" above "aerated concrete"
    silently reintroduces a 4x error. This fails if that happens."""
    def index_of(fragment):
        for i, (keys, _) in enumerate(_STD_VOLUME_DENSITY):
            if fragment in keys:
                return i
        raise AssertionError(f"{fragment} not in the table")

    assert index_of("aerated concrete") < index_of("concrete")
    assert index_of("lightweight concrete") < index_of("concrete")
    assert index_of("reinforced concrete") < index_of("steel")
    assert index_of("glass wool") < index_of("glass")
    assert index_of("cement board") < index_of("cement")
    assert index_of("cement mortar") < index_of("cement")


def test_ordinary_materials_still_resolve():
    for name, expected in [
        ("Ready mix concrete M25", 2400), ("Steel rebar", 7850),
        ("Float glass", 2500), ("Portland cement", 1440),
        ("River sand", 1600), ("Burnt clay brick", 1800),
        ("Gypsum board", 1200), ("Aluminium window frame", 2700),
    ]:
        assert _std_volume_density(name) == expected, name


def test_an_unknown_material_gets_nothing_rather_than_a_guess():
    assert _std_volume_density("Unobtainium cladding") is None
    assert _std_volume_density("") is None
    assert _std_volume_density(None) is None


# --- the fallback must not touch the shared catalogue ----------------------

class _FakeEPD:
    """Stands in for an EPD; the point is that save() must never be called."""
    def __init__(self, name, declared_unit="kg", conversions=None):
        self.name = name
        self.declared_unit = declared_unit
        self.conversions = conversions
        self.saved = False

    def save(self, **kwargs):
        self.saved = True

    def get_available_units(self):
        return {self.declared_unit}


def test_the_fallback_is_recorded_on_the_row_not_saved_to_the_epd():
    """It used to persist the guess into the shared EPD, from the PREVIEW step,
    so merely looking at a BoQ changed an EPD every other building uses. 117
    catalogue EPDs already carry a value matching one of these constants and
    there is no way to tell which were measured."""
    epd = _FakeEPD("Ready mix concrete M25")
    row = {"status": "bad_unit", "epd": epd, "unit": "m3"}
    fixed = autofix_conversions([row])

    assert fixed == 1
    assert epd.saved is False, "the shared EPD must not be written to"
    assert epd.conversions is None, "the EPD's own conversions must be untouched"
    assert row["assumed_density"] == 2400
    assert row["status"] == "ok"
    assert "this import only" in row["reason"]


def test_a_published_density_always_wins():
    """610 catalogue EPDs carry their own measured density - glass wool's is
    16, against a fallback of 100. The published figure is never overridden."""
    epd = _FakeEPD("Glass wool", conversions=[
        {"name": "volume density", "unit": "kg/m^3", "value": "16"}])
    row = {"status": "bad_unit", "epd": epd, "unit": "m3"}
    assert autofix_conversions([row]) == 0
    assert "assumed_density" not in row
    assert epd.saved is False


def test_area_and_linear_mismatches_are_still_refused():
    """Mass to volume is a defensible constant. Area, linear and count need
    geometry the BoQ does not carry, so they stay flagged rather than guessed."""
    for unit in ("m2", "m", "pcs"):
        epd = _FakeEPD("Ready mix concrete M25")
        row = {"status": "bad_unit", "epd": epd, "unit": unit}
        assert autofix_conversions([row]) == 0
        assert row["status"] == "bad_unit"
