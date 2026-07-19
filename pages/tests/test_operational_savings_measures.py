"""Tests for the operational-carbon (Layer 3) optimisation measures.

Covers ``get_operational_savings_measures``:
- multiplicative per-system measure stacking
- already-installed measures locked to zero saving (every record flagged)
- "no equipment records -> measure available (OFF)" edge case
- BMS applied last on the whole-building electricity total
- refrigerant Scope-1 saving summed across chiller + AC
"""

from decimal import Decimal

import pytest

from pages.tests.test_impact_calculation import create_epd  # noqa: F401 (fixture)

from pages.models.epd import EPDImpact, Impact, ImpactCategoryKey, LifeCycleStage, Unit
from pages.models.building import OperationalProduct, Building
from pages.models.building_operation.energy_summary import EnergySummary
from pages.models.building_operation.ventilation import VentilationSystem
from pages.models.building_operation.lighting import LightingSystem
from pages.models.building_operation.chilling import (
    CoolingSystemChiller,
    RefrigerantGWP,
)
from pages.models.climate_type import ClimateType

from pages.views.building.building_stats import get_operational_savings_measures


# ---------------------------------------------------------------------------
# Fixtures (mirrors test_operational_carbon_by_system.py)
# ---------------------------------------------------------------------------

@pytest.fixture
def create_impact_B6():
    def _create_impact_B6(impact):
        return Impact.objects.create(
            impact_category=impact, life_cycle_stage=LifeCycleStage.B6,
        )
    return _create_impact_B6


@pytest.fixture
def create_epd_impact():
    def _create_epd_impact(epd, value, impact):
        return EPDImpact.objects.create(epd=epd, impact=impact, value=value)
    return _create_epd_impact


@pytest.fixture
def create_building():
    def _create_building(total_floor_area=Decimal("100")):
        climate, _ = ClimateType.objects.get_or_create(name="cold")
        return Building.objects.create(
            name="Test Building", climate_zone=climate,
            total_floor_area=total_floor_area,
        )
    return _create_building


@pytest.fixture
def create_electricity_epd(create_epd, create_impact_B6, create_epd_impact):
    def _create(gwp_value, declared_amount=Decimal("1")):
        epd = create_epd("electricity grid mix", Unit.KWH, [])
        epd.declared_amount = declared_amount
        epd.save()
        create_epd_impact(epd, gwp_value, create_impact_B6(ImpactCategoryKey.GWP))
        return epd
    return _create


@pytest.fixture
def setup_grid(create_electricity_epd):
    """Attach a 0.5 kgCO2/kWh electricity EPD to a building."""
    def _setup(building):
        epd = create_electricity_epd(Decimal("0.5"))
        OperationalProduct.objects.create(
            building=building, epd=epd, quantity=Decimal("1"), input_unit=Unit.KWH,
        )
    return _setup


# ---------------------------------------------------------------------------
# Per-system stacking
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_ventilation_measures_stack_multiplicatively(
    create_building, setup_grid,
):
    building = create_building(total_floor_area=Decimal("100"))
    setup_grid(building)
    # ventilation baseline = 1000 kWh * 0.5 / 100 = 5.0 kgCO2eq/m2/yr
    EnergySummary.objects.create(building=building, ventilation_kwh=Decimal("1000"))

    result = get_operational_savings_measures(building)
    vent = next(s for s in result["systems"] if s["key"] == "ventilation")

    # DCV 30% then VSD 20% multiplicatively: 5.0 -> 3.5 -> 2.8
    assert vent["baseline"] == 5.0
    assert vent["optimized"] == 2.8
    dcv = next(m for m in vent["measures"] if m["key"] == "vent_dcv")
    vsd = next(m for m in vent["measures"] if m["key"] == "vent_vsd")
    assert dcv["saving"] == 1.5   # 5.0 * 0.30
    assert vsd["saving"] == 0.7   # 3.5 * 0.20
    assert dcv["installed"] is False and vsd["installed"] is False


@pytest.mark.django_db
def test_no_records_measure_available_off(create_building, setup_grid):
    """A system with energy but no equipment records shows measures available/OFF."""
    building = create_building(total_floor_area=Decimal("100"))
    setup_grid(building)
    EnergySummary.objects.create(building=building, lighting_kwh=Decimal("400"))

    result = get_operational_savings_measures(building)
    lighting = next(s for s in result["systems"] if s["key"] == "lighting")
    # No LightingSystem records -> not "all LED", measures available (OFF).
    for m in lighting["measures"]:
        assert m["installed"] is False


@pytest.mark.django_db
def test_all_records_flagged_locks_measure(create_building, setup_grid):
    """A measure is installed only when every record of that system has the flag."""
    building = create_building(total_floor_area=Decimal("100"))
    setup_grid(building)
    EnergySummary.objects.create(building=building, ventilation_kwh=Decimal("1000"))

    common = dict(
        building=building, ventilation_type="AHU", ventilation_capacity="M3H",
        baseline_efficiency_w_cmh=2, operation_hours_per_workday=8,
        workdays_per_week=5, workweeks_per_year=50, total_power_input_kw=1,
        air_flow_rate=500, number_of_units_installed=1,
    )
    # Both records have DCV -> DCV installed; only one has VSD -> VSD not installed.
    VentilationSystem.objects.create(
        **common, demand_controlled_ventilation=True, variable_speed_drives=True,
    )
    VentilationSystem.objects.create(
        **common, demand_controlled_ventilation=True, variable_speed_drives=False,
    )

    result = get_operational_savings_measures(building)
    vent = next(s for s in result["systems"] if s["key"] == "ventilation")
    dcv = next(m for m in vent["measures"] if m["key"] == "vent_dcv")
    vsd = next(m for m in vent["measures"] if m["key"] == "vent_vsd")
    assert dcv["installed"] is True and dcv["saving"] == 0.0
    assert vsd["installed"] is False and vsd["saving"] > 0.0


@pytest.mark.django_db
def test_all_led_locks_led_measure(create_building, setup_grid):
    building = create_building(total_floor_area=Decimal("100"))
    setup_grid(building)
    EnergySummary.objects.create(building=building, lighting_kwh=Decimal("400"))

    LightingSystem.objects.create(
        building=building, room_type="COMMERCIAL_GENERAL", area_of_room=100,
        lighting_bulb_type="LED_PANEL", number_of_bulbs=10,
        light_bulb_power_rating_w=20, operation_hours_per_workday=8,
        workdays_per_week=5, workweeks_per_year=50, sensors_installed=False,
    )
    result = get_operational_savings_measures(building)
    lighting = next(s for s in result["systems"] if s["key"] == "lighting")
    led = next(m for m in lighting["measures"] if m["key"] == "light_led")
    assert led["installed"] is True and led["saving"] == 0.0


# ---------------------------------------------------------------------------
# BMS (applies last on the electricity total)
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_bms_applies_to_electricity_total(create_building, setup_grid):
    building = create_building(total_floor_area=Decimal("100"))
    setup_grid(building)
    # Lighting only, no equipment records so no measures apply -> optimized == baseline.
    EnergySummary.objects.create(building=building, lift_escalator_kwh=Decimal("1000"))

    result = get_operational_savings_measures(building)
    lift = next(s for s in result["systems"] if s["key"] == "lift")
    # lift baseline = 1000 * 0.5 / 100 = 5.0; both lift measures available (no records)
    # optimized_lift = 5.0 * 0.8 (regen 20%) * 0.6 (vvvf 40%) = 2.4
    assert lift["baseline"] == 5.0
    assert lift["optimized"] == 2.4
    # BMS = 20% of optimized electricity total (2.4) = 0.48
    assert result["bms"]["saving"] == 0.48


# ---------------------------------------------------------------------------
# Refrigerant Scope-1
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_refrigerant_scope1_saving(create_building, setup_grid):
    building = create_building(total_floor_area=Decimal("100"))
    setup_grid(building)
    EnergySummary.objects.create(building=building, cooling_kwh=Decimal("1000"))

    RefrigerantGWP.objects.get_or_create(refrigerant_code="R-717", defaults={"gwp_value": 0})
    RefrigerantGWP.objects.get_or_create(refrigerant_code="R-410A", defaults={"gwp_value": 2088})

    # 10 kg R-410A (GWP 2088), 2% leakage, GFA 100, target GWP 0 (R-717):
    # 10 * 0.02 * (2088 - 0) / 100 = 4.176 -> 4.18
    CoolingSystemChiller.objects.create(
        building=building, chiller_type="air_cooled", year_of_installation=2020,
        refrigerant_type="R-410A", refrigerant_quantity_kg=Decimal("10"),
        total_cooling_load_rt=100, number_of_chillers=1,
        baseline_refrigerant_emission_factor=2088,
        baseline_leakage_factor_percent=2,
    )

    result = get_operational_savings_measures(building)
    assert result["refrigerant"]["has_saving"] is True
    assert result["refrigerant"]["saving"] == 4.18


@pytest.mark.django_db
def test_refrigerant_already_natural_zero_saving(create_building, setup_grid):
    building = create_building(total_floor_area=Decimal("100"))
    setup_grid(building)
    EnergySummary.objects.create(building=building, cooling_kwh=Decimal("1000"))

    RefrigerantGWP.objects.get_or_create(refrigerant_code="R-717", defaults={"gwp_value": 0})
    RefrigerantGWP.objects.get_or_create(refrigerant_code="R-290", defaults={"gwp_value": 3})

    # R-290 GWP 3, target lowest natural = R-717 GWP 0; 3 > 0 so a tiny saving exists,
    # but if the unit is already at the target it contributes nothing. Use R-717 here.
    CoolingSystemChiller.objects.create(
        building=building, chiller_type="air_cooled", year_of_installation=2020,
        refrigerant_type="R-717", refrigerant_quantity_kg=Decimal("10"),
        total_cooling_load_rt=100, number_of_chillers=1,
        baseline_refrigerant_emission_factor=0,
        baseline_leakage_factor_percent=2,
    )

    result = get_operational_savings_measures(building)
    assert result["refrigerant"]["saving"] == 0.0
    assert result["refrigerant"]["has_saving"] is False


# ---------------------------------------------------------------------------
# Totals
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_totals_and_lifetime(create_building, setup_grid):
    building = create_building(total_floor_area=Decimal("100"))
    building.reference_period = 50
    building.save()
    setup_grid(building)
    EnergySummary.objects.create(building=building, lift_escalator_kwh=Decimal("1000"))

    result = get_operational_savings_measures(building)
    # baseline_total = 5.0; lifetime = 5.0 * 50 = 250
    assert result["baseline_total"] == 5.0
    assert result["baseline_total_lifetime"] == 250
    assert result["reduction_pct"] > 0
    assert result["optimized_total"] < result["baseline_total"]
