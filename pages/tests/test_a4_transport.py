"""A4 transport: journeys are legs, one per transport mode.

The feature originally collapsed every scenario into a single distance and a
single "blended" emission factor. For India that reported 0.070 kgCO2e/tonne-km
over 50 km and 0.01286 over 3,150 km, which reads as the emission factor falling
as the distance grows. The arithmetic was right — a 3,150 km import is 95% sea,
and sea is about seven times cleaner per tonne-km than road — but the number on
screen was a weighted average of two different vehicles, not a property of
anything real.

These tests pin the behaviour that replaced it: every leg carries its own mode's
factor, and no blended factor is reported.
"""
from decimal import Decimal

import pytest

from pages.scripts.a4a5 import defaults as D
from pages.scripts.a4a5.compute import material_a4_a5


# --- the journeys themselves -------------------------------------------------

def test_local_is_a_single_road_leg():
    legs = D.scenario_legs("local", "India")
    assert legs == [{"mode": "road", "km": 50.0, "ef": 0.07}]


def test_imported_is_a_sea_leg_then_a_road_leg():
    legs = D.scenario_legs("imported", "India")
    assert [l["mode"] for l in legs] == ["sea", "road"]
    assert legs[0] == {"mode": "sea", "km": 3000.0, "ef": 0.01}
    assert legs[1] == {"mode": "road", "km": 150.0, "ef": 0.07}


def test_every_leg_carries_its_own_modes_published_factor():
    """No leg may show a factor that is not one of the country's mode factors."""
    for country in ("India", "Thailand", "Cambodia", "Vietnam", "Indonesia"):
        ef = D.transport_ef(country)
        allowed = {ef["road"], ef["rail"], ef["sea"]}
        for scenario in ("local", "national", "imported"):
            for leg in D.scenario_legs(scenario, country):
                assert leg["ef"] in allowed, (country, scenario, leg)


def test_leg_distances_sum_to_the_scenario_distance():
    for country in ("India", "Cambodia"):
        for scenario, expected in (("local", 50.0), ("national", 300.0), ("imported", 3150.0)):
            legs = D.scenario_legs(scenario, country)
            assert D.scenario_total_km(legs) == expected


# --- the thing that looked wrong ---------------------------------------------

def test_carbon_per_tonne_rises_with_distance():
    """The reported A4 must never fall as the journey gets longer."""
    for country in ("India", "Thailand", "Cambodia", "Vietnam", "Indonesia"):
        per_tonne = [D.legs_tonne_km_co2(D.scenario_legs(s, country))
                     for s in ("local", "national", "imported")]
        assert per_tonne == sorted(per_tonne), (country, per_tonne)


def test_no_blended_emission_factor_is_reported():
    """`effective_ef` exists only to fill half-specified overrides, never for display."""
    _, _, meta = material_a4_a5(
        a1a3_per_m2=Decimal("10"), mass_kg=1000, floor_area=100,
        country_name="India", category_name="Steel")
    assert "ef" not in meta, "a single blended factor is what confused readers"
    assert meta["legs"], "the journey must be reported leg by leg"


def test_the_old_blend_is_what_fell_with_distance():
    """Documents the original fault, so nobody reintroduces the blend."""
    local = D.effective_ef(D.scenario_legs("local", "India"))
    imported = D.effective_ef(D.scenario_legs("imported", "India"))
    assert local == pytest.approx(0.070)
    assert imported == pytest.approx(0.012857, abs=1e-5)
    assert imported < local          # the blend really does fall...
    # ...while the carbon it represents rises, which is why legs are reported.
    assert (D.legs_tonne_km_co2(D.scenario_legs("imported", "India"))
            > D.legs_tonne_km_co2(D.scenario_legs("local", "India")))


# --- rail --------------------------------------------------------------------

def test_rail_is_actually_used_now():
    """The rail factor sat unused in every country table before this change."""
    modes = [l["mode"] for l in D.scenario_legs("national", "India")]
    assert "rail" in modes


def test_rail_only_applies_to_the_national_scenario():
    for scenario in ("local", "imported"):
        modes = [l["mode"] for l in D.scenario_legs(scenario, "India")]
        assert "rail" not in modes


def test_a_country_with_no_rail_freight_gets_none():
    """Cambodia's rail share is 0, so its national haul is all road."""
    legs = D.scenario_legs("national", "Cambodia")
    assert [l["mode"] for l in legs] == ["road"]
    assert legs[0]["km"] == 300.0


def test_rail_share_splits_the_land_distance():
    legs = {l["mode"]: l for l in D.scenario_legs("national", "India")}
    assert legs["rail"]["km"] == pytest.approx(180.0)   # 300 x 0.60
    assert legs["road"]["km"] == pytest.approx(120.0)   # the remainder


# --- the A4 figure -----------------------------------------------------------

def test_a4_is_tonnes_times_the_summed_leg_carbon():
    # 2,000 kg = 2 t imported into India: 3000x0.01 + 150x0.07 = 40.5 kg/t
    a4, _, meta = material_a4_a5(
        a1a3_per_m2=Decimal("0"), mass_kg=2000, floor_area=100,
        country_name="India", category_name="Steel", scenario="imported")
    assert meta["kgco2e_per_tonne"] == pytest.approx(40.5)
    assert float(a4) == pytest.approx(2 * 40.5 / 100)   # per m2 of floor area


def test_steel_defaults_to_imported_and_concrete_to_local():
    assert D.default_scenario("Structural steel") == "imported"
    assert D.default_scenario("Ready mixed concrete") == "local"
    assert D.default_scenario("Something else entirely") == "national"


# --- per-material overrides --------------------------------------------------

def test_an_explicit_distance_and_factor_collapse_to_one_leg():
    _, _, meta = material_a4_a5(
        a1a3_per_m2=Decimal("0"), mass_kg=1000, floor_area=100,
        country_name="India", category_name="Steel",
        scenario="imported", distance_km=400, ef=0.05)
    assert meta["legs"] == [{"mode": "custom", "km": 400.0, "ef": 0.05}]
    assert meta["kgco2e_per_tonne"] == pytest.approx(20.0)


def test_a_distance_alone_keeps_the_scenarios_effective_factor():
    _, _, meta = material_a4_a5(
        a1a3_per_m2=Decimal("0"), mass_kg=1000, floor_area=100,
        country_name="India", category_name="Steel",
        scenario="imported", distance_km=1000)
    assert len(meta["legs"]) == 1
    assert meta["legs"][0]["ef"] == pytest.approx(0.01286, abs=1e-5)


def test_a_factor_alone_keeps_the_scenarios_distance():
    _, _, meta = material_a4_a5(
        a1a3_per_m2=Decimal("0"), mass_kg=1000, floor_area=100,
        country_name="India", category_name="Steel",
        scenario="imported", ef=0.09)
    assert meta["legs"] == [{"mode": "custom", "km": 3150.0, "ef": 0.09}]


# --- A5 and the guards -------------------------------------------------------

def test_a5w_counts_waste_against_a1a3_plus_a4_and_adds_disposal():
    a4, a5w, meta = material_a4_a5(
        a1a3_per_m2=Decimal("100"), mass_kg=1000, floor_area=100,
        country_name="India", category_name="Ready mixed concrete",
        waste_rate=0.05)
    expected = Decimal("0.05") * (Decimal("100") + a4) + (
        Decimal("1000") * Decimal("0.05") * Decimal(str(D.DISPOSAL_EF_PER_KG)) / Decimal("100"))
    assert float(a5w) == pytest.approx(float(expected))


def test_no_mass_means_no_a4_rather_than_a_crash():
    a4, a5w, meta = material_a4_a5(
        a1a3_per_m2=Decimal("10"), mass_kg=None, floor_area=100,
        country_name="India", category_name="Steel")
    assert a4 == 0 and a5w == 0
    assert "mass not derivable" in meta["note"]
    assert meta["legs"], "the journey is still reported so the user sees why it is zero"


def test_no_floor_area_means_no_a4_rather_than_a_crash():
    a4, a5w, meta = material_a4_a5(
        a1a3_per_m2=Decimal("10"), mass_kg=1000, floor_area=0,
        country_name="India", category_name="Steel")
    assert a4 == 0 and a5w == 0
    assert meta["note"] == "no floor area"


def test_an_unknown_country_falls_back_without_raising():
    legs = D.scenario_legs("national", "Atlantis")
    assert [l["mode"] for l in legs] == ["road"]          # default rail share is 0
    assert legs[0]["ef"] == D.DEFAULT_TRANSPORT_EF["road"]
