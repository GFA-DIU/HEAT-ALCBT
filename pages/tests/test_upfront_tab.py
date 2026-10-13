"""The Upfront Carbon panel template.

Rendered against a fabricated context rather than a built-up Building graph:
what is being checked here is the panel's own behaviour — that it states the
journey behind each A4 figure, that it only warns about the rail assumption
where that assumption actually applies, and that it degrades to a sentence
rather than an empty table when there is nothing to show.

The A4 arithmetic itself is covered in test_a4_transport.py.
"""
from django.template.loader import render_to_string

from pages.scripts.a4a5 import defaults as D


def _ctx(**over):
    """A panel context shaped like the view's, for India unless told otherwise."""
    journeys = [dict(key=k,
                     label=D.SCENARIOS[k]["label"],
                     legs=D.scenario_legs(k, "India"),
                     legs_text=D.describe_legs(D.scenario_legs(k, "India")),
                     distance_km=D.scenario_total_km(D.scenario_legs(k, "India")),
                     kgco2e_per_tonne=round(D.legs_tonne_km_co2(D.scenario_legs(k, "India")), 4))
                for k in ("local", "national", "imported")]
    ctx = {
        "building": type("B", (), {"id": "00000000-0000-0000-0000-000000000000"})(),
        "country": "India",
        "floor_area": 500.0,
        "totals": {"a1a3": 501.29, "a4": 11.17, "a5w": 27.58, "upfront": 540.04},
        "groups": [{
            "name": "Foundation", "a1a3": 100.0, "a4": 2.0, "a5w": 5.0,
            "rows": [{
                "id": 1, "name": "Ready-mix concrete C25/30", "category": "Ready mixed concrete",
                "mass_kg": 12000.0, "a1a3": 100.0, "scenario": "local",
                "a4": 2.0, "a5w": 5.0, "waste_pct": 5.0,
                "legs_text": "road 50 km @ 0.07", "legs": D.scenario_legs("local", "India"),
                "kgco2e_per_tonne": 3.5, "overridden": False,
            }],
        }],
        "journeys": journeys,
        "rail_share_pct": 60,
        "ef_source": D.transport_ef("India")["source"],
        "disposal_ef": D.DISPOSAL_EF_PER_KG,
        "scenario_choices": D.SCENARIO_CHOICES,
        "has_rows": True,
    }
    ctx.update(over)
    return ctx


def _render(**over):
    return render_to_string("pages/building/upfront_tab.html", _ctx(**over))


def test_the_panel_states_the_journey_behind_every_a4_figure():
    html = _render()
    assert "sea 3000 km @ 0.01 + road 150 km @ 0.07" in html
    assert "rail 180 km @ 0.008 + road 120 km @ 0.07" in html
    assert "road 50 km @ 0.07" in html


def test_the_four_headline_numbers_are_shown():
    html = _render()
    for frag in ("501.3", "11.17", "27.58", "540.0"):
        assert frag in html, frag


def test_no_single_blended_emission_factor_is_printed():
    """0.01286 was the number that made readers think the factor fell with distance."""
    assert "0.01286" not in _render()


def test_the_rail_assumption_is_flagged_where_it_applies():
    html = _render()
    assert "Assumption, not sourced" in html
    assert "60" in html


def test_no_rail_warning_where_there_is_no_rail():
    """Cambodia's share is 0, so the warning would be noise."""
    html = _render(country="Cambodia", rail_share_pct=0)
    assert "Assumption, not sourced" not in html


def test_a_building_with_nothing_to_show_says_so():
    html = _render(has_rows=False)
    assert "No materials with a resolvable mass yet" in html
    assert "<table" not in html


def test_a_missing_building_renders_a_sentence_not_a_broken_panel():
    html = render_to_string("pages/building/upfront_tab.html", {"not_found": True})
    assert "Building not found" in html
    assert "<table" not in html


def test_the_panel_says_epd_declared_a4_is_not_used():
    """A reader must not think these came off the EPD."""
    html = _render()
    assert "not used" in html


def test_every_data_icon_exists_in_the_registry():
    """Ten data-icon names once rendered as empty boxes across seven templates."""
    import re
    from pathlib import Path
    tpl = Path(__file__).resolve().parents[2] / "templates/pages/building/upfront_tab.html"
    registry = (Path(__file__).resolve().parents[2] / "static/js/icons.js").read_text(
        encoding="utf-8", errors="replace")
    for name in re.findall(r'data-icon="([^"]+)"', tpl.read_text(encoding="utf-8")):
        assert name in registry, f"data-icon '{name}' is not in static/js/icons.js"
