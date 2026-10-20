"""Name matching that landed on the wrong material while looking like a hit.

Both faults below were found by importing a dummy BoQ against the real
catalogue. Both produced a carbon number, which is why neither was noticed:
the row said "ok" and the material was wrong.
"""
import pytest

from pages.views.building.import_building import (
    CROSS_COUNTRY, _changes_material, _epd_tokens, _fuzzy_epd_pick,
    _lookup_structural_epd,
)


# --- words that change what a material is ----------------------------------

@pytest.mark.parametrize("query,candidate", [
    # Glass-reinforced concrete is thin cladding, not structural concrete.
    ("Reinforced concrete", "Glass reinforced concrete"),
    # The mortar that joins the blocks is not the blocks.
    ("AAC block", "AAC block mortar - TPI - M319"),
    ("Reinforced concrete", "Reinforced concrete pipe (tongue-and-groove type)"),
    ("Cement", "Cement plaster"),
    ("Concrete", "Concrete formwork"),
])
def test_a_different_product_is_not_a_match(query, candidate):
    assert _changes_material(query, candidate)


@pytest.mark.parametrize("query,candidate", [
    # The word is in the query too, so it is not an added difference.
    ("Float glass", "Float glass, 6mm"),
    ("Cement mortar", "Cement mortar 1:4"),
    # Elaboration, not a different product. These must NOT be rejected.
    ("AAC block", "Autoclaved aerated concrete (AAC) solid blocks"),
    ("Concrete", "Ready-mix concrete C25/30"),
    ("Steel rebar", "Steel reinforcement (steel rebar)"),
])
def test_an_elaborated_name_is_still_a_match(query, candidate):
    assert not _changes_material(query, candidate)


# --- plurals ---------------------------------------------------------------

def test_a_plural_matches_its_singular():
    """Without this, "AAC block" shares only the abbreviation with the
    catalogue's "AAC solid blocks" and the correct EPD scores below the
    confidence cutoff while a wrong one above it wins."""
    assert "block" in _epd_tokens("AAC solid blocks")
    assert _epd_tokens("block") & _epd_tokens("blocks")


def test_a_double_s_word_is_not_stemmed():
    assert "glass" in _epd_tokens("Float glass")


# --- the picker ------------------------------------------------------------

def test_the_picker_refuses_a_product_changing_candidate():
    best, _ = _fuzzy_epd_pick("Reinforced concrete", ["Glass reinforced concrete"])
    assert best is None, "glass-reinforced cladding is not structural concrete"


def test_the_picker_still_takes_an_elaborated_candidate():
    best, _ = _fuzzy_epd_pick(
        "AAC block",
        ["Autoclaved aerated concrete (AAC) solid blocks", "Float glass", "Sand"],
    )
    assert best == "Autoclaved aerated concrete (AAC) solid blocks"


# --- against a seeded catalogue --------------------------------------------
#
# Seeded rather than borrowed from the developer's database: a test that skips
# when the catalogue is absent cannot fail, and both faults below were the kind
# that only a real lookup exposes.

@pytest.fixture
def cambodia(db):
    from cities_light.models import Country
    return Country.objects.get_or_create(
        code2="KH",
        defaults={"name": "Cambodia", "continent": "AS", "slug": "cambodia"},
    )[0]


@pytest.fixture
def germany(db):
    from cities_light.models import Country
    return Country.objects.get_or_create(
        code2="DE",
        defaults={"name": "Germany", "continent": "EU", "slug": "germany"},
    )[0]


@pytest.fixture
def catalogue(db, cambodia, germany):
    """The four names that produced the two wrong matches."""
    from pages.models.epd import EPD, EPDType, Unit

    def make(name, country):
        return EPD.objects.create(
            name=name,
            names=[{"value": name, "lang": "en"}],
            UUID=f"test-{abs(hash((name, country.code2)))}",
            declared_unit=Unit.KG,
            conversions=[],
            type=EPDType.GENERIC,
            country=country,
            public=True,
            draft=False,
            declared_amount=1,
        )

    return {
        "grc": make("Glass reinforced concrete", cambodia),
        "pipe": make("Reinforced concrete pipe (tongue-and-groove type)", cambodia),
        "aac": make("Autoclaved aerated concrete (AAC) solid blocks", cambodia),
        "mortar": make("AAC block mortar - TPI - M319", germany),
    }


@pytest.mark.django_db
def test_reinforced_concrete_refuses_rather_than_taking_cladding(catalogue):
    """It scored 0.94 against "Glass reinforced concrete" and imported as it.
    No plain structural "Reinforced concrete" EPD exists, so the honest answer
    is no match: an absent figure is visible, a wrong one is not."""
    epd, err = _lookup_structural_epd("Reinforced concrete", "Cambodia")
    assert epd is None, f"took {epd.name!r} instead of refusing"
    assert err and "not found" in err.lower()


@pytest.mark.django_db
def test_aac_block_takes_the_block_not_the_mortar(catalogue):
    """The mortar that joins the blocks carries a different factor entirely,
    and its name is the closer string, so string distance alone chose it."""
    epd, err = _lookup_structural_epd("AAC block", "Cambodia")
    assert epd is not None, "the correct block EPD was in the catalogue"
    assert epd.name == "Autoclaved aerated concrete (AAC) solid blocks"
    assert err is not CROSS_COUNTRY


@pytest.mark.django_db
def test_the_own_country_match_wins_over_the_closer_name_abroad(catalogue):
    """The localised GWP is the point of a per-country catalogue, so a
    confident same-country match beats a closer name somewhere else."""
    epd, _ = _lookup_structural_epd("AAC block", "Cambodia")
    assert epd.country.name == "Cambodia"
