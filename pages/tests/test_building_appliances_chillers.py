import pytest
from django.db import IntegrityError
from pages.models import (
    Building,
    CategorySubcategory,
    BuildingCategory,
    BuildingSubcategory,
    Refrigerant,
    Chiller,
    ChillerBenchmark
)
from cities_light.models import Country


# -----------------------
# BUILDING FIXTURES
# -----------------------
@pytest.fixture
def building(db):
    return Building.objects.create(
        name="Building 1",
        total_floor_area=100
    )


@pytest.fixture
def category(db):
    return BuildingCategory.objects.create(name="Commercial")


@pytest.fixture
def subcategory(db):
    return BuildingSubcategory.objects.create(name="Office")


@pytest.fixture
def category_subcategory(category, subcategory):
    return CategorySubcategory.objects.create(
        category=category,
        subcategory=subcategory
    )


# -----------------------
# COUNTRY FIXTURE
# -----------------------
@pytest.fixture
def country(db):
    country_obj, _ = Country.objects.get_or_create(
        name="Rwanda",
    )
    return country_obj


# -----------------------
# REFRIGERANT FIXTURE
# -----------------------
@pytest.fixture
def refrigerant(db):
    refrigerant_obj, _ = Refrigerant.objects.get_or_create(name="R-410A")
    return refrigerant_obj


# -----------------------
# CHILLER FIXTURE
# -----------------------
@pytest.fixture
def chiller(building, refrigerant):
    return Chiller.objects.create(
        building=building,
        chiller_type='water',
        year_of_installation=2020,
        operation_hours_per_workday=8,
        workdays_per_week=6,
        workweeks_per_year=50,
        refrigerant_type=refrigerant,
        refrigerant_quantity_kg=25.0,
        total_cooling_load_rt=50.0,
        baseline_cooling_efficiency_kw_rt=1.5,
        vsd_installed='yes',
        heat_recovery_installed='no'
    )


# -----------------------
# CHILLER BENCHMARK FIXTURE
# -----------------------
@pytest.fixture
def chiller_benchmark(country, category_subcategory, refrigerant):
    return ChillerBenchmark.objects.create(
        country=country,
        building_type=category_subcategory,
        chiller_type='water',
        refrigerant_type=refrigerant,
        benchmark_efficiency_kw_rt=1.4,
        benchmark_cop=6.5,
        benchmark_iplv=6.8,
        benchmark_emission_factor=1430,
        benchmark_leakage_factor=5
    )


# -----------------------
# TESTS
# -----------------------
def test_refrigerant_creation(refrigerant):
    assert refrigerant.name == "R-410A"


def test_chiller_creation(chiller, building, refrigerant):
    assert chiller.building == building
    assert chiller.refrigerant_type == refrigerant
    assert chiller.vsd_installed == 'yes'
    assert chiller.heat_recovery_installed == 'no'


def test_chiller_unique_constraints(building, refrigerant):
    # first chiller
    Chiller.objects.create(
        building=building,
        chiller_type='water',
        year_of_installation=2021,
        refrigerant_type=refrigerant,
        refrigerant_quantity_kg=20,
        total_cooling_load_rt=40,
        vsd_installed='yes',
        heat_recovery_installed='no'
    )

    # duplicate building + chiller_type should fail
    with pytest.raises(IntegrityError):
        Chiller.objects.create(
            building=building,
            chiller_type='water',
            year_of_installation=2022,
            refrigerant_type=Refrigerant.objects.get_or_create(name="R-134a")[0],
            refrigerant_quantity_kg=30,
            total_cooling_load_rt=45,
            vsd_installed='no',
            heat_recovery_installed='yes'
        )


def test_chiller_benchmark_creation(chiller_benchmark, country, category_subcategory, refrigerant):
    assert chiller_benchmark.country == country
    assert chiller_benchmark.building_type == category_subcategory
    assert chiller_benchmark.refrigerant_type == refrigerant
    assert chiller_benchmark.benchmark_cop == 6.5
