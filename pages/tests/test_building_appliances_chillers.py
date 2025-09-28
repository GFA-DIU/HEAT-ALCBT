# tests/test_models.py
import pytest
from django.core.exceptions import ValidationError
from pages.models import (
    Building,
    BuildingOperation,
    CoolingSystemChiller,
    CoolingSystemAirConditioner,
    VentilationSystem,
    LightingSystem,
    LiftEscalatorSystem,
    HotWaterSystem,
    OperationEnergyDemand,
    EnergyConsumption,
    RefrigerantType,
    VentilationType,
    RoomType,
    LightingBulbType,
    HotWaterSystemType,
    FuelType,
    EnergySourceType,
    EnergyUnit,
)

from decimal import Decimal


@pytest.fixture
@pytest.mark.django_db
def building():
    return Building.objects.create(
        name="Minimal Building",
        climate_zone="Tropical",
        total_floor_area=Decimal("500"),
        reference_period=30
    )


@pytest.mark.django_db
def test_building_operation_creation(building):
    op = BuildingOperation.objects.create(
        building=building,
        number_of_residents=100,
        operation_hours_per_workday=8,
        workdays_per_week=5,
        workweeks_per_year=50,
        renewable_energy_percent=20,
        energy_monitoring_control_systems=True
    )
    assert op.building == building
    assert op.number_of_residents == 100
    assert op.operation_hours_per_workday == 8


@pytest.mark.django_db
@pytest.mark.parametrize("invalid_hours", [0, 25])
def test_building_operation_invalid_hours(building, invalid_hours):
    op = BuildingOperation(
        building=building,
        number_of_residents=10,
        operation_hours_per_workday=invalid_hours,
        workdays_per_week=5,
        workweeks_per_year=50,
        renewable_energy_percent=20
    )
    with pytest.raises(ValidationError):
        op.full_clean()


@pytest.mark.django_db
def test_cooling_system_chiller_creation(building):
    chiller = CoolingSystemChiller.objects.create(
        building=building,
        chiller_type="water_cooled",
        year_of_installation=2020,
        refrigerant_type=RefrigerantType.R134A,
        refrigerant_quantity_kg=50,
        total_cooling_load_rt=100,
        number_of_chillers=2
    )
    assert chiller.building == building
    assert chiller.chiller_type == "water_cooled"
    assert chiller.refrigerant_type == RefrigerantType.R134A


@pytest.mark.django_db
def test_cooling_system_air_conditioner_creation(building):
    ac = CoolingSystemAirConditioner.objects.create(
        building=building,
        ac_type="vrv",
        year_of_installation=2021,
        refrigerant_type=RefrigerantType.R410A,
        refrigerant_quantity_kg=30,
        total_cooling_load_rt=50,
        number_of_units=3
    )
    assert ac.building == building
    assert ac.ac_type == "vrv"


@pytest.mark.django_db
def test_ventilation_system_creation(building):
    ventilation = VentilationSystem.objects.create(
        building=building,
        ventilation_type=VentilationType.AHU,
        ventilation_capacity=VentilationType.AHU,
        baseline_efficiency_w_cmh=100,
        total_power_input_w=500,
        air_flow_rate=1000,
        number_of_units_installed=2
    )
    assert ventilation.building == building
    assert ventilation.ventilation_type == VentilationType.AHU


@pytest.mark.django_db
def test_lighting_system_creation(building):
    lighting = LightingSystem.objects.create(
        building=building,
        room_type=RoomType.OFFICE_CONFERENCE,
        area_of_room=50,
        lighting_bulb_type=LightingBulbType.LED,
        number_of_bulbs=10,
        operation_hours_per_workday=8,
        workdays_per_week=5,
        workweeks_per_year=50,
        light_bulb_power_rating_w=10
    )
    assert lighting.room_type == RoomType.OFFICE_CONFERENCE
    assert lighting.lighting_bulb_type == LightingBulbType.LED


@pytest.mark.django_db
def test_lift_escalator_system_creation(building):
    lift = LiftEscalatorSystem.objects.create(
        building=building,
        number_of_lifts=4,
        lift_regenerative_features=True,
        vvvf_sleep_mode=True
    )
    assert lift.building == building
    assert lift.number_of_lifts == 4


@pytest.mark.django_db
def test_hot_water_system_creation(building):
    hot_water = HotWaterSystem.objects.create(
        building=building,
        system_type=HotWaterSystemType.BOILER,
        operation_hours_per_workday=8,
        workdays_per_week=5,
        workweeks_per_year=50,
        fuel_type=FuelType.ELECTRICITY,
        fuel_consumption=100,
        power_input_kw=50,
        baseline_efficiency_cop=90,
        baseline_equipment_efficiency_percentage=80,
        number_of_equipments=1
    )
    assert hot_water.system_type == HotWaterSystemType.BOILER
    assert hot_water.fuel_type == FuelType.ELECTRICITY


@pytest.mark.django_db
def test_operation_energy_demand_and_consumption(building):
    demand = OperationEnergyDemand.objects.create(
        building=building,
        renewable_energy_adoption=20
    )
    assert demand.building == building
    assert demand.renewable_energy_adoption == 20

    consumption = EnergyConsumption.objects.create(
        operation_demand=demand,
        energy_source=EnergySourceType.ELECTRICITY,
        consumption_value=1000,
        unit=EnergyUnit.KWH_A
    )
    assert consumption.operation_demand == demand
    assert consumption.energy_source == EnergySourceType.ELECTRICITY
