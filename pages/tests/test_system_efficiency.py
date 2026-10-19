"""Layer 2 - equipment-efficiency replacement benchmarks.

Layer 3 asks what a control bolted onto existing equipment saves. Layer 2 asks
what replacing the equipment saves. It needs a unit bridge BEAT did not have:
the workbook states cooling in kW/RT, while BEAT stores whatever was on the
label - COP, EER, ISEER, CSPF or SEER.
"""
from decimal import Decimal

import pytest

from pages.views.building.system_efficiency_data import (
    HIGHER_IS_BETTER, KW_PER_REFRIGERATION_TON, LOWER_IS_BETTER,
    LPD_BENCHMARKS, SYSTEM_EFFICIENCY, cop_to_kw_per_rt,
    efficiency_saving_fraction, kw_per_rt_to_cop, resolve_system_benchmark,
)


# --- the unit bridge -------------------------------------------------------

def test_the_ton_constant_matches_the_one_the_cooling_form_uses():
    """A building entered in tons and benchmarked here must not pass through
    two slightly different conversions."""
    from pages.forms.cooling_system_form import CAPACITY_CONVERSION
    assert CAPACITY_CONVERSION["ton"] == KW_PER_REFRIGERATION_TON


def test_cop_converts_to_the_indian_split_baseline():
    """India's 0.85 kW/RT split baseline is a COP of about 4.14."""
    assert round(float(cop_to_kw_per_rt(4.14)), 2) == 0.85
    assert round(float(kw_per_rt_to_cop(0.85)), 2) == 4.14


def test_the_conversion_round_trips():
    for cop in (2.5, 3.0, 4.14, 5.3):
        back = kw_per_rt_to_cop(cop_to_kw_per_rt(cop))
        assert abs(float(back) - cop) < 0.001


@pytest.mark.parametrize("bad", [0, -1, None, "", "abc"])
def test_the_conversion_refuses_rather_than_guesses(bad):
    assert cop_to_kw_per_rt(bad) is None
    assert kw_per_rt_to_cop(bad) is None


# --- the saving fraction ---------------------------------------------------

def test_a_lower_is_better_figure_saves_the_proportional_difference():
    """A 1.05 kW/RT chiller replaced by a 0.94 one uses 0.94/1.05 of the
    energy, so it saves 10.5%."""
    s = efficiency_saving_fraction(1.05, 0.94, LOWER_IS_BETTER)
    assert round(s, 3) == 0.105


def test_a_higher_is_better_figure_saves_the_inverse_difference():
    """A COP 3.0 heat pump replaced by a COP 3.5 one saves 1 - 3.0/3.5."""
    s = efficiency_saving_fraction(3.0, 3.5, HIGHER_IS_BETTER)
    assert round(s, 3) == 0.143


@pytest.mark.parametrize("direction,current,target", [
    (LOWER_IS_BETTER, 0.80, 0.94),    # already better than the target
    (LOWER_IS_BETTER, 0.94, 0.94),    # exactly at it
    (HIGHER_IS_BETTER, 4.0, 3.3),     # already better
    (HIGHER_IS_BETTER, 3.3, 3.3),
])
def test_equipment_already_at_the_target_saves_nothing(direction, current, target):
    """Never negative. "Your chiller beats best practice" is not a saving the
    building can bank."""
    assert efficiency_saving_fraction(current, target, direction) == 0.0


# --- the data guard --------------------------------------------------------

def test_the_split_unit_leed_value_is_refused_not_used():
    """1_System_Efficiency gives the split unit LEED 1.36 kW/RT against
    national baselines of 0.80 to 0.85 - a "best practice" 60% worse than the
    average building. Used unchecked it yields a negative saving, which would
    render as a building that gets worse by modernising."""
    for country in ("India", "Indonesia", "Thailand", "Cambodia"):
        r = resolve_system_benchmark("split", country, "leed")
        assert r is not None
        assert r["credible"] is False, country
        assert r["best_practice"] is None, country


def test_a_credible_best_practice_is_used():
    r = resolve_system_benchmark("air_cooled_chiller", "India", "leed")
    assert r["credible"] is True
    assert r["best_practice"] == 0.94
    assert r["national"] == 1.05
    assert r["unit"] == "kW/RT"


def test_edge_is_usable_for_splits_even_though_leed_is_not():
    """EDGE gives 0.86, which is better than Indonesia's 0.84? No - it is not,
    so Indonesia refuses EDGE too. India at 0.85 also refuses it. The guard is
    per country, not per row."""
    assert resolve_system_benchmark("split", "India", "edge")["credible"] is False
    assert resolve_system_benchmark("split", "Vietnam", "edge")["credible"] is True


# --- blanks are never synthesised -----------------------------------------

def test_a_blank_country_cell_reports_no_benchmark():
    """VRV/VRF has no Thailand row. 0_README: blank means no benchmark was
    published; do not synthesise."""
    assert resolve_system_benchmark("vrv", "Thailand") is None
    assert resolve_system_benchmark("hot_water_heat_pump", "Indonesia") is None


def test_a_blank_best_practice_cell_is_not_filled_in():
    r = resolve_system_benchmark("vrv", "India", "leed")
    assert r["national"] == 0.86
    assert r["best_practice"] is None


def test_india_has_no_residential_lighting_density():
    assert LPD_BENCHMARKS["Residential"]["India"] is None
    assert LPD_BENCHMARKS["Residential"]["Indonesia"] == 7.53


def test_an_unknown_system_or_country_returns_nothing():
    assert resolve_system_benchmark("teleporter", "India") is None
    assert resolve_system_benchmark("split", "Narnia") is None


# --- the table matches the workbook ---------------------------------------

def test_every_system_declares_its_direction_and_unit():
    for key, spec in SYSTEM_EFFICIENCY.items():
        assert spec["direction"] in (LOWER_IS_BETTER, HIGHER_IS_BETTER), key
        assert spec["unit"], key
        assert spec["national"], key


# --- the target, and why it falls back ------------------------------------

def test_a_credible_best_practice_becomes_the_target():
    """Both LEED (0.94) and EDGE (0.85) beat India's 1.05 baseline, and EDGE is
    the lower of the two, so EDGE is the target."""
    r = resolve_system_benchmark("air_cooled_chiller", "India")
    assert r["target"] == 0.85
    assert r["target_basis"] == "EDGE"
    assert r["best_practice"] == 0.85


def test_the_better_of_leed_and_edge_wins():
    """Air-cooled chiller: LEED 0.94, EDGE 0.85. Lower is better, so EDGE."""
    r = resolve_system_benchmark("air_cooled_chiller", "Indonesia")
    assert r["target"] == 0.85
    assert r["target_basis"] == "EDGE"


def test_the_split_unit_falls_back_to_the_national_baseline():
    """Neither LEED (1.36, refused) nor EDGE (0.86, not better than 0.85) is
    usable for an Indian split. Without the fallback Layer 2 would be silent
    for 287 of the 351 air conditioners in the database."""
    r = resolve_system_benchmark("split", "India")
    assert r["best_practice"] is None
    assert r["target"] == 0.85
    assert r["target_basis"] == "national baseline"


def test_the_ui_can_always_tell_which_target_it_got():
    """A national average must never be presented as best practice."""
    for key in SYSTEM_EFFICIENCY:
        for country in ("India", "Indonesia", "Vietnam", "Thailand", "Cambodia"):
            r = resolve_system_benchmark(key, country)
            if r is None:
                continue
            assert r["target_basis"] in ("LEED", "EDGE", "national baseline")
            if r["target_basis"] == "national baseline":
                assert r["best_practice"] is None


def test_a_poor_split_saves_against_the_national_baseline():
    """COP 2.8 is 1.256 kW/RT against India's 0.85 baseline: a 32% saving."""
    r = resolve_system_benchmark("split", "India")
    current = float(cop_to_kw_per_rt(2.8))
    s = efficiency_saving_fraction(current, r["target"], r["direction"])
    assert round(s, 2) == 0.32


def test_a_split_already_beating_the_baseline_saves_nothing():
    current = float(cop_to_kw_per_rt(5.0))     # 0.703 kW/RT, better than 0.85
    r = resolve_system_benchmark("split", "India")
    assert efficiency_saving_fraction(current, r["target"], r["direction"]) == 0.0


def test_window_units_have_no_benchmark_row_at_all():
    """20 window units across four countries. The workbook publishes no row,
    so they report nothing rather than borrowing the split figure."""
    assert resolve_system_benchmark("window", "India") is None
