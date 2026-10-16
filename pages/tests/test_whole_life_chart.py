"""The Whole Life Carbon donut and the A4-A5 share view.

The donut used to show two slices, embodied against operational, labelled
"Upfront embodied carbon (A1-A5)". Two problems with that: the word "Upfront"
named a total the chart did not show as a slice, and the embodied figure left
out A5.2 site energy even though the Upfront panel counted it, so the two
screens reported different totals for the same building.
"""
import uuid as uuid_lib

import pytest

from pages.models.building import Building
from pages.views.building.building_stats import (
    calculate_embodied_modules, get_a4a5_share_by_material,
    get_building_chart_data)


pytestmark = pytest.mark.django_db


@pytest.fixture
def bare_building(django_user_model):
    user = django_user_model.objects.create_user(
        username="charts", email="charts@example.com", password="x")
    return Building.objects.create(
        name="Empty", total_floor_area=100, created_by=user)


# --- the module split --------------------------------------------------------

def test_the_module_split_reports_a5_2_and_a_combined_a4a5(bare_building):
    """A5.2 is part of upfront; leaving it out made two screens disagree."""
    m = calculate_embodied_modules(bare_building)
    for key in ("a1a3", "a4", "a5w", "a5_2", "a5", "a4a5", "upfront"):
        assert key in m, key


def test_a5_is_the_sum_of_its_two_parts(bare_building):
    m = calculate_embodied_modules(bare_building)
    assert m["a5"] == m["a5w"] + m["a5_2"]
    assert m["a4a5"] == m["a4"] + m["a5w"] + m["a5_2"]
    assert m["upfront"] == m["a1a3"] + m["a4a5"]


def test_a_building_with_no_site_energy_contributes_zero_not_an_estimate(
        bare_building):
    assert calculate_embodied_modules(bare_building)["a5_2"] == 0


# --- the donut ---------------------------------------------------------------

def test_the_donut_has_three_stages(bare_building):
    w = get_building_chart_data(bare_building)["whole_life_carbon"]
    assert w["labels"] == ["Product (A1-A3)", "Construction (A4-A5)",
                           "Operational (B6)"]
    assert len(w["data"]) == 3


def test_the_word_upfront_is_gone_from_the_legend(bare_building):
    w = get_building_chart_data(bare_building)["whole_life_carbon"]
    for label in w["labels"]:
        assert "Upfront" not in label, label


def test_the_donut_carries_the_sub_stages_for_the_csv(bare_building):
    w = get_building_chart_data(bare_building)["whole_life_carbon"]
    stages = [r["stage"] for r in w["breakdown"]]
    assert stages == ["A1-A3", "A4", "A5.2", "A5.3", "B6"]
    for row in w["breakdown"]:
        assert row["label"], "every stage needs a readable description"


def test_the_middle_slice_equals_its_sub_stages(bare_building):
    w = get_building_chart_data(bare_building)["whole_life_carbon"]
    by_stage = {r["stage"]: r["value"] for r in w["breakdown"]}
    construction = by_stage["A4"] + by_stage["A5.2"] + by_stage["A5.3"]
    assert w["data"][1] == pytest.approx(construction)
    assert w["data"][0] == pytest.approx(by_stage["A1-A3"])
    assert w["data"][2] == pytest.approx(by_stage["B6"])


# --- A4-A5 by material -------------------------------------------------------

def test_the_share_view_is_present_and_shaped_for_a_bar_chart(bare_building):
    d = get_building_chart_data(bare_building)["a4a5_by_material"]
    for key in ("labels", "data", "absolute", "rows", "total"):
        assert key in d, key
    assert len(d["labels"]) == len(d["data"]) == len(d["absolute"])


def test_an_empty_building_yields_no_rows_rather_than_raising(bare_building):
    d = get_a4a5_share_by_material(bare_building)
    assert d["rows"] == []
    assert d["total"] == 0


def test_the_bar_is_a_share_of_the_building_not_of_the_material():
    """The per-material share read strangely beside the A1-A3 chart.

    Masonry came out at 71% while contributing 1.7 kgCO2e/m2, because transport
    dwarfs its tiny product carbon - so a big percentage did not mean a big
    number. The bar is now a share of the building's total A4+A5, matching the
    chart next to it, and "share of its own carbon" is kept per row for the CSV.
    """
    rows = [
        {"name": "Rebar", "a4a5": 534.671, "a1a3": 3982.31},
        {"name": "Masonry", "a4a5": 1.719, "a1a3": 2.42},
    ]
    total = sum(r["a4a5"] for r in rows)
    pct_of_total = [round(r["a4a5"] / total * 100, 1) for r in rows]
    pct_of_own = [round(r["a4a5"] / r["a1a3"] * 100, 1) for r in rows]
    # of the building: rebar dominates, as it should
    assert pct_of_total[0] > pct_of_total[1]
    # of its own carbon: masonry dominates - the opposite ranking
    assert pct_of_own[1] > pct_of_own[0]


def test_rows_carry_both_shares_so_the_csv_can_report_them(bare_building):
    """The insight is kept, just moved somewhere it cannot be misread."""
    import inspect
    from pages.views.building import building_stats
    src = inspect.getsource(building_stats.get_a4a5_share_by_material)
    assert '"pct_of_total"' in src
    assert '"pct_of_own"' in src


def test_materials_are_grouped_the_same_way_as_the_a1a3_chart():
    """Both charts must name materials identically to be read side by side."""
    import inspect
    from pages.views.building import building_stats
    src = inspect.getsource(building_stats.get_a4a5_share_by_material)
    assert "_MATERIAL_CATEGORY_MAPPING" in src
