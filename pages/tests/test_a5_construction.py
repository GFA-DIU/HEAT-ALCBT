"""A5.2 — construction site energy.

RICS WLCA 2nd ed. splits A5 four ways. BEAT models two of them, A5.2 (site
energy) and A5.3 (construction waste), and says so rather than labelling the
pair "A5".

The two are computed in opposite directions and these tests pin that: A5.3 is
per material (waste % of that material's A1-A3 + A4), while A5.2 is per project
(one meter reading for the whole build). They must not be merged into a single
loop or a single reported number without the split being visible.
"""
from decimal import Decimal

import pytest

from pages.scripts.a4a5 import fuels
from pages.scripts.a4a5.construction import construction_energy, scope_note


class _Epd:
    """Minimal stand-in: the calculation only needs a name and a B6 factor."""

    def __init__(self, name, factor):
        self.name = name
        self._factor = factor

    def get_gwp_impact_sum(self, stage):
        return Decimal(str(self._factor)) if stage == "b6" else None


class _Entry:
    def __init__(self, epd, quantity, unit):
        self.id = None
        self.epd = epd
        self.quantity = Decimal(str(quantity))
        self.input_unit = unit


# --- converting what a site actually records --------------------------------

def test_kwh_needs_no_conversion():
    assert fuels.to_kwh(1000, "kwh", "Electricity")[0] == 1000.0


def test_litres_of_diesel_become_kwh_via_density_and_calorific_value():
    kwh, how = fuels.to_kwh(4200, "l", "Diesel")
    # 4200 l x 0.832 kg/l x 43.0 MJ/kg / 3.6
    assert kwh == pytest.approx(4200 * 0.832 * 43.0 / 3.6, rel=1e-6)
    assert "0.832" in how and "43" in how


def test_kilograms_need_no_density():
    kwh, how = fuels.to_kwh(500, "kg", "Liquefied Petroleum Gas (LPG)")
    assert kwh == pytest.approx(500 * 47.3 / 3.6, rel=1e-6)
    assert "kg/l" not in how


def test_megajoules_convert_directly():
    assert fuels.to_kwh(360, "mj", "Natural Gas")[0] == pytest.approx(100.0)


def test_a_fuel_sold_by_mass_refuses_litres_rather_than_guessing_a_density():
    kwh, why = fuels.to_kwh(200, "l", "Liquefied Petroleum Gas (LPG)")
    assert kwh is None
    assert "enter it in kg" in why


def test_a_non_fuel_is_refused():
    kwh, why = fuels.to_kwh(50, "l", "Marble slab")
    assert kwh is None
    assert "not a fuel" in why


def test_fuel_names_map_to_the_right_carrier():
    assert fuels.carrier_for("Heavy Fuel Oil") == "fuel_oil"
    assert fuels.carrier_for("Light Fuel Oil") == "fuel_oil"
    assert fuels.carrier_for("Liquefied Petroleum Gas (LPG)") == "lpg"
    assert fuels.carrier_for("Firewood (Log Wood)") == "wood"
    assert fuels.carrier_for("Natural Gas") == "natural_gas"
    assert fuels.carrier_for("Lignite") == "lignite"
    assert fuels.carrier_for("Ready-mix concrete C25/30") is None


def test_fuel_oil_wins_over_oil_and_gas_names_do_not_collide():
    """Ordering matters: 'Heavy Fuel Oil' must not be read as LPG or wood."""
    assert fuels.carrier_for("Heavy Fuel Oil") != "lpg"
    assert fuels.carrier_for("Natural Gas") != "lpg"


# --- the A5.2 figure ---------------------------------------------------------

def test_a5_2_is_kwh_times_the_carriers_factor_over_floor_area():
    elec = _Epd("Electricity", 0.59)
    total, rows, _ = construction_energy([_Entry(elec, 18000, "kwh")], 469)
    assert rows[0]["kwh"] == 18000.0
    assert rows[0]["kgco2e"] == pytest.approx(18000 * 0.59, rel=1e-6)
    assert float(total) == pytest.approx(18000 * 0.59 / 469, rel=1e-6)


def test_several_carriers_sum():
    rows = [_Entry(_Epd("Electricity", 0.59), 18000, "kwh"),
            _Entry(_Epd("Diesel", 0.30), 4200, "l")]
    total, _, _ = construction_energy(rows, 469)
    diesel_kwh = 4200 * 0.832 * 43.0 / 3.6
    expected = (18000 * 0.59 + diesel_kwh * 0.30) / 469
    assert float(total) == pytest.approx(expected, rel=1e-6)


def test_nothing_entered_reports_zero_and_says_the_total_is_understated():
    """No benchmark is invented - there is no sourced kWh/m2 for these countries."""
    total, rows, notes = construction_energy([], 469)
    assert total == 0
    assert rows == []
    assert any("understated" in n for n in notes)


def test_an_entry_that_cannot_be_converted_is_reported_not_silently_dropped():
    bad = _Entry(_Epd("Liquefied Petroleum Gas (LPG)", 0.24), 200, "l")
    good = _Entry(_Epd("Electricity", 0.59), 1000, "kwh")
    total, rows, notes = construction_energy([bad, good], 100)
    assert rows[0]["a5_2"] is None and rows[0]["problem"]
    assert rows[1]["a5_2"] is not None
    assert float(total) == pytest.approx(1000 * 0.59 / 100)   # only the good one counts
    assert any("could not be counted" in n for n in notes)


def test_an_epd_with_no_carbon_factor_is_flagged():
    total, rows, _ = construction_energy([_Entry(_Epd("Diesel", 0), 100, "l")], 100)
    assert rows[0]["problem"] == "no B6 carbon factor on this EPD"
    assert total == 0


def test_no_floor_area_is_flagged_rather_than_dividing_by_zero():
    total, rows, _ = construction_energy([_Entry(_Epd("Electricity", 0.59), 100, "kwh")], 0)
    assert rows[0]["problem"] == "no floor area"
    assert total == 0


def test_an_assumed_density_is_declared_to_the_user():
    """Diesel litres lean on a density that is not from IPCC - say so."""
    _, _, notes = construction_energy(
        [_Entry(_Epd("Diesel", 0.30), 4200, "l")], 469)
    assert any("assumed density" in n for n in notes)
    assert fuels.describes_assumed_density("Diesel") is True
    assert fuels.describes_assumed_density("Liquefied Petroleum Gas (LPG)") is False


def test_the_conversion_is_shown_so_it_can_be_audited():
    _, rows, _ = construction_energy([_Entry(_Epd("Diesel", 0.30), 4200, "l")], 469)
    assert "IPCC 2006" in rows[0]["conversion"]


# --- scope -------------------------------------------------------------------

def test_the_scope_note_names_what_is_missing():
    note = scope_note()
    for fragment in ("A5.2", "A5.3", "A5.1", "A5.4", "not included"):
        assert fragment in note, fragment
