import pytest
import pages.views.energy_calculations as ec


# --------------------
# 1. Overall Building Performance
# --------------------

def test_potential_energy_saving_building():
    baseline_eui = 250.0
    benchmark_eui = 200.0
    gfa = 1000.0
    expected = (baseline_eui - benchmark_eui) * gfa
    assert ec.potential_energy_saving_building(baseline_eui, benchmark_eui, gfa) == expected


# --------------------
# 2. Chiller System
# --------------------

def test_potential_energy_saving_chiller_replace():
    total_cooling_load = 100.0
    baseline_eff = 1.2
    benchmark_eff = 1.0
    hours = 2000.0
    expected = total_cooling_load * (baseline_eff - benchmark_eff) * hours
    assert ec.potential_energy_saving_chiller_replace(total_cooling_load, baseline_eff, benchmark_eff, hours) == expected


@pytest.mark.parametrize("baseline_eff,total_cooling_load,hours,percent,expected", [
    (1.2, 100.0, 2000.0, 10.0, 1.2 * 100.0 * 2000.0 * 0.10),
    (1.5, 50.0, 1000.0, 5.0, 1.5 * 50.0 * 1000.0 * 0.05),
])
def test_potential_energy_saving_chiller_vsd(baseline_eff, total_cooling_load, hours, percent, expected):
    assert pytest.approx(ec.potential_energy_saving_chiller_vsd(baseline_eff, total_cooling_load, hours, percent)) == expected


@pytest.mark.parametrize("baseline_eff,total_cooling_load,hours,percent,expected", [
    (1.2, 100.0, 2000.0, 15.0, 1.2 * 100.0 * 2000.0 * 0.15),
])
def test_potential_energy_saving_chiller_heat_recovery(baseline_eff, total_cooling_load, hours, percent, expected):
    assert pytest.approx(ec.potential_energy_saving_chiller_heat_recovery(baseline_eff, total_cooling_load, hours, percent)) == expected


# --------------------
# 3. Split Unit / VRV
# --------------------

def test_potential_energy_saving_split_vrv():
    total_cooling_load = 200.0
    baseline = 1.5
    benchmark = 1.2
    hours = 1500.0
    expected = total_cooling_load * (baseline - benchmark) * hours
    assert ec.potential_energy_saving_split_vrv(total_cooling_load, baseline, benchmark, hours) == expected


# --------------------
# 4. Ventilation System
# --------------------

def test_potential_energy_saving_ventilation_replace():
    baseline = 1.5
    benchmark = 1.0
    hours = 1000.0
    expected = (baseline - benchmark) * hours
    assert ec.potential_energy_saving_ventilation_replace(baseline, benchmark, hours) == expected


def test_potential_energy_saving_ventilation_vsd_and_dcv():
    total_power = 500.0
    hours = 2000.0
    vsd_percent = 20.0
    dcv_percent = 25.0

    expected_vsd = total_power * hours * (vsd_percent / 100.0)
    expected_dcv = total_power * hours * (dcv_percent / 100.0)

    assert ec.potential_energy_saving_ventilation_vsd(total_power, hours, vsd_percent) == expected_vsd
    assert ec.potential_energy_saving_ventilation_dcv(total_power, hours, dcv_percent) == expected_dcv


# --------------------
# 5. Lighting System
# --------------------

def test_baseline_lpd_value():
    total_power = 120.0  # W
    area = 60.0  # m2
    expected = total_power / area
    assert ec.baseline_lpd_value(total_power, area) == expected


def test_potential_energy_saving_lighting_replace():
    room_areas = [100.0, 200.0]
    baseline_lpd = 15.0  # W/m2
    benchmark_lpd = 10.0  # W/m2
    hours = 3000.0

    expected = (100.0 * (baseline_lpd - benchmark_lpd) * hours + 200.0 * (baseline_lpd - benchmark_lpd) * hours) / 1000.0
    assert ec.potential_energy_saving_lighting_replace(room_areas, baseline_lpd, benchmark_lpd, hours) == expected


def test_potential_energy_saving_lighting_sensors():
    total_power_input = 1000.0  # kW
    building_hours = 4000.0
    percent = 10.0
    annual = total_power_input * building_hours
    expected = annual * (percent / 100.0)
    assert ec.potential_energy_saving_lighting_sensors(total_power_input, building_hours, percent) == expected


# --------------------
# 6. Lift & Escalator System
# --------------------

def test_annual_lift_energy_consumption_and_savings():
    total_building = 100000.0
    expected_consumption = total_building * 0.075
    assert ec.annual_lift_energy_consumption(total_building) == expected_consumption

    # regenerative
    percent_regen = 15.0
    expected_regen = expected_consumption * (percent_regen / 100.0)
    assert ec.potential_energy_saving_lift_regenerative(total_building, percent_regen) == expected_regen

    # vvvf
    percent_vvvf = 20.0
    expected_vvvf = expected_consumption * (percent_vvvf / 100.0)
    assert ec.potential_energy_saving_lift_vvvf(total_building, percent_vvvf) == expected_vvvf


# --------------------
# 7. Hot Water System
# --------------------

def test_potential_energy_saving_hotwater_replace_and_heat_recovery():
    baseline = 1.5
    benchmark = 1.0
    hours = 2000.0
    expected_replace = (baseline - benchmark) * hours
    assert ec.potential_energy_saving_hotwater_replace(baseline, benchmark, hours) == expected_replace

    percent = 20.0
    annual = baseline * hours
    expected_heat_recovery = annual * (percent / 100.0)
    assert ec.potential_energy_saving_hotwater_heat_recovery(baseline, hours, percent) == expected_heat_recovery


# --------------------
# 8. Smart Building System
# --------------------

def test_potential_energy_saving_smart_system():
    total = 500000.0
    percent = 10.0
    expected = total * (percent / 100.0)
    assert ec.potential_energy_saving_smart_system(total, percent) == expected


# --------------------
# 9. Renewable Energy System
# --------------------

def test_potential_energy_saving_renewable():
    total = 600000.0
    renewable_pct = 20.0
    expected = total * (renewable_pct / 100.0)
    assert ec.potential_energy_saving_renewable(total, renewable_pct) == expected


# --------------------
# 10. Carbon Emission Reduction Calculator
# --------------------

def test_avoided_emission_refrigerants():
    quantities = [100.0, 200.0]
    baseline_leakage = 0.1
    baseline_factor = 2.0
    benchmark_leakage = 0.05
    benchmark_factor = 1.0

    baseline_total = sum(q * baseline_leakage * baseline_factor for q in quantities)
    benchmark_total = sum(q * benchmark_leakage * benchmark_factor for q in quantities)
    expected = baseline_total - benchmark_total

    assert ec.avoided_emission_refrigerants(quantities, baseline_leakage, baseline_factor, benchmark_leakage, benchmark_factor) == expected


def test_avoided_emission_hotwater_and_scope2_and_total():
    fuel_consumption = 1000.0
    baseline_factor = 0.5
    benchmark_factor = 0.3
    expected_hotwater = fuel_consumption * (baseline_factor - benchmark_factor)
    assert ec.avoided_emission_hotwater(fuel_consumption, baseline_factor, benchmark_factor) == expected_hotwater

    total_saving = 5000.0
    grid_factor = 0.7
    expected_scope2 = total_saving * grid_factor
    assert ec.avoided_emission_scope2(total_saving, grid_factor) == expected_scope2

    # assume no refrigerant savings in this test
    avoided_refrigerants = 0.0
    total_expected = avoided_refrigerants + expected_hotwater + expected_scope2
    assert ec.total_carbon_emission_reduction(
        avoided_refrigerants, expected_hotwater, expected_scope2
    ) == total_expected
