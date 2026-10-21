"""Two faults on the savings tab, both visible only in a browser.

The equipment-replacement panel is an OPERATIONAL measure but sits outside
both column containers, so it rendered under the Embodied tab as well -
offering to replace chillers and light fittings on a panel about materials.

The operational waterfall's eight measure names overprinted each other in a
narrow column.
"""
from pathlib import Path

import pytest

TEMPLATE = Path("templates/pages/building/savings_tab.html")


@pytest.fixture(scope="module")
def source():
    return TEMPLATE.read_text(encoding="utf-8")


# --- the equipment panel belongs to the operational view -------------------

def test_the_equipment_panel_has_an_id_to_toggle(source):
    assert 'id="savings-equipment-replacement"' in source


def test_it_starts_hidden(source):
    """The Embodied view is the default, so the panel must not be visible
    until Operational is selected."""
    start = source.index('id="savings-equipment-replacement"')
    opening_tag = source[start:source.index(">", start)]
    assert "hidden" in opening_tag, opening_tag


def test_the_toggle_shows_it_only_for_operational(source):
    assert "getElementById('savings-equipment-replacement')" in source
    after = source.split("getElementById('savings-equipment-replacement')", 1)[1][:260]
    assert "classList.toggle('hidden', view !== 'operational')" in after


def test_every_toggled_block_is_handled_by_the_toggle(source):
    """The panel was missed because it lives outside both columns. Any other
    block in that position would be missed the same way, so check each id the
    toggle is responsible for is actually referenced in it."""
    toggled = [
        "savings-embodied-left", "savings-operational-left",
        "savings-embodied-strategies", "savings-operational-strategies",
        "benchmark-embodied", "benchmark-operational",
        "savings-equipment-replacement",
    ]
    fn = source.split("window.toggleSavingsView", 1)[1]
    for element_id in toggled:
        assert "'%s'" % element_id in fn, element_id


# --- the waterfall labels --------------------------------------------------

def test_the_operational_waterfall_is_horizontal(source):
    """Eight measure names across a narrow column overprinted each other.
    Rotating ran them off the panel; wrapping onto two lines still collided."""
    chart = source.split("function drawOperationalWaterfall", 1)[1]
    assert "indexAxis: 'y'" in chart


def test_the_measure_names_are_on_the_category_axis(source):
    """With indexAxis 'y' the measures are on y and the values on x. Leaving
    the old axis config in place would put the kgCO2 title beside the names."""
    chart = source.split("function drawOperationalWaterfall", 1)[1]
    value_axis = chart.split("x: { beginAtZero: true", 1)[1][:200]
    assert "kgCO2eq/m2/yr" in value_axis


def test_no_label_is_dropped(source):
    """autoSkip would hide measures rather than overlap them, which trades one
    unreadable chart for a misleading one."""
    chart = source.split("function drawOperationalWaterfall", 1)[1]
    assert "autoSkip: false" in chart


def test_the_canvas_is_tall_enough_for_one_row_per_measure(source):
    """Horizontal bars need height per row. At the old 200px, eight measures
    had 25px each."""
    canvas = source.split('id="savings-operational-reduction-chart"', 1)[0]
    height = canvas.rsplit("h-[", 1)[1].split("]", 1)[0]
    assert height.endswith("px")
    assert int(height[:-2]) >= 300, height
