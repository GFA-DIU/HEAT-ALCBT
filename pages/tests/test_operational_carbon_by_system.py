"""Tests for operational carbon by building system (Systems tab).

Covers:
- ``_derive_grid_emission_factor``: grid factor = electricity EPD B6 GWP / declared_amount
- ``get_operational_carbon_by_system``: per-system intensity (kWh * grid_factor / floor_area)
"""

from decimal import Decimal

import pytest

from pages.tests.test_impact_calculation import create_epd  # noqa: F401 (fixture)

from pages.models.epd import EPDImpact, Impact, ImpactCategoryKey, LifeCycleStage, Unit
from pages.models.building import OperationalProduct, Building
from pages.models.building_operation.energy_summary import EnergySummary
from pages.models.climate_type import ClimateType

from pages.views.building.building_stats import (
    _derive_grid_emission_factor,
    get_operational_carbon_by_system,
)


@pytest.fixture
def create_impact_B6():
    def _create_impact_B6(impact):
        return Impact.objects.create(
            impact_category=impact,
            life_cycle_stage=LifeCycleStage.B6,
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
            name="Test Building",
            climate_zone=climate,
            total_floor_area=total_floor_area,
        )

    return _create_building


@pytest.fixture
def create_operationalproduct():
    def _create_operationalproduct(building, epd, quantity, unit):
        return OperationalProduct.objects.create(
            building=building,
            epd=epd,
            quantity=quantity,
            input_unit=unit,
        )

    return _create_operationalproduct


@pytest.fixture
def create_energy_summary():
    def _create_energy_summary(building, **kwh):
        return EnergySummary.objects.create(building=building, **kwh)

    return _create_energy_summary


@pytest.fixture
def create_electricity_epd(create_epd, create_impact_B6, create_epd_impact):
    """Create a kWh-declared electricity EPD with a B6 GWP value."""

    def _create_electricity_epd(gwp_value, declared_amount=Decimal("1")):
        epd = create_epd("electricity grid mix", Unit.KWH, [])
        epd.declared_amount = declared_amount
        epd.save()
        impact_gwp = create_impact_B6(ImpactCategoryKey.GWP)
        create_epd_impact(epd, gwp_value, impact_gwp)
        return epd

    return _create_electricity_epd


# ---------------------------------------------------------------------------
# _derive_grid_emission_factor
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_grid_factor_basic(
    create_building, create_electricity_epd, create_operationalproduct
):
    building = create_building()
    epd = create_electricity_epd(Decimal("0.5"), declared_amount=Decimal("1"))
    create_operationalproduct(building, epd, Decimal("100"), Unit.KWH)

    assert _derive_grid_emission_factor(building) == Decimal("0.5")


@pytest.mark.django_db
def test_grid_factor_with_declared_amount(
    create_building, create_electricity_epd, create_operationalproduct
):
    building = create_building()
    epd = create_electricity_epd(Decimal("0.5"), declared_amount=Decimal("2"))
    create_operationalproduct(building, epd, Decimal("100"), Unit.KWH)

    assert _derive_grid_emission_factor(building) == Decimal("0.25")


@pytest.mark.django_db
def test_grid_factor_no_electricity_epd(create_building):
    building = create_building()
    assert _derive_grid_emission_factor(building) == Decimal("0")


# ---------------------------------------------------------------------------
# get_operational_carbon_by_system
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_system_carbon_basic(
    create_building,
    create_electricity_epd,
    create_operationalproduct,
    create_energy_summary,
):
    building = create_building(total_floor_area=Decimal("100"))
    epd = create_electricity_epd(Decimal("0.5"))
    create_operationalproduct(building, epd, Decimal("1"), Unit.KWH)
    create_energy_summary(
        building, cooling_kwh=Decimal("1000"), lighting_kwh=Decimal("500")
    )

    result = get_operational_carbon_by_system(building)

    # cooling = 1000 * 0.5 / 100 = 5.0 ; lighting = 500 * 0.5 / 100 = 2.5
    assert result["labels"] == ["Cooling systems", "Lighting systems"]
    assert result["absolute"] == [5.0, 2.5]
    assert result["total"] == 7.5
    assert result["data"][0] == pytest.approx(66.7, abs=0.1)
    assert result["data"][1] == pytest.approx(33.3, abs=0.1)
    assert "warning" not in result


@pytest.mark.django_db
def test_system_carbon_floor_area_zero_blocks(
    create_building, create_electricity_epd, create_operationalproduct, create_energy_summary
):
    building = create_building(total_floor_area=Decimal("0"))
    epd = create_electricity_epd(Decimal("0.5"))
    create_operationalproduct(building, epd, Decimal("1"), Unit.KWH)
    create_energy_summary(building, cooling_kwh=Decimal("1000"))

    result = get_operational_carbon_by_system(building)

    assert result["labels"] == []
    assert result["total"] == 0
    assert result.get("blocked") is True


@pytest.mark.django_db
def test_system_carbon_grid_factor_zero_warns(
    create_building, create_energy_summary
):
    building = create_building(total_floor_area=Decimal("100"))
    # No electricity EPD -> grid factor 0
    create_energy_summary(building, cooling_kwh=Decimal("1000"))

    result = get_operational_carbon_by_system(building)

    assert result["labels"] == ["Cooling systems"]
    assert result["absolute"] == [0.0]
    assert result["total"] == 0
    assert result.get("warning") == "grid_factor_zero"


@pytest.mark.django_db
def test_system_carbon_no_energy_summary(create_building):
    building = create_building(total_floor_area=Decimal("100"))
    result = get_operational_carbon_by_system(building)

    assert result == {"labels": [], "data": [], "absolute": [], "total": 0}


@pytest.mark.django_db
def test_system_carbon_blank_systems_excluded(
    create_building, create_electricity_epd, create_operationalproduct, create_energy_summary
):
    building = create_building(total_floor_area=Decimal("100"))
    epd = create_electricity_epd(Decimal("0.5"))
    create_operationalproduct(building, epd, Decimal("1"), Unit.KWH)
    # cooling has value; others blank/zero -> excluded
    create_energy_summary(
        building, cooling_kwh=Decimal("1000"), ventilation_kwh=Decimal("0")
    )

    result = get_operational_carbon_by_system(building)

    assert result["labels"] == ["Cooling systems"]
    assert result["total"] == 5.0
