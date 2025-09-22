import pytest
from decimal import Decimal
from pages.models import Building, EPD, OperationalProduct, Assembly, BuildingAssembly, CategorySubcategory

@pytest.mark.django_db
def test_building_operational_info_assignment():
    # Create EPD objects with all required fields
    epd1 = EPD.objects.create(
        name="EPD 1",
        names="EPD One",
        type="Material",
        declared_amount=0,
        source="Unknown"
    )
    epd2 = EPD.objects.create(
        name="EPD 2",
        names="EPD Two",
        type="Material",
        declared_amount=0,
        source="Unknown"
    )

    # Create building
    building = Building.objects.create(
        name="Operational Building",
        climate_zone="Temperate",
        total_floor_area=Decimal("1000"),
        reference_period=50
    )

    # Assign operational components via through model
    OperationalProduct.objects.create(building=building, epd=epd1, quantity=1)
    OperationalProduct.objects.create(building=building, epd=epd2, quantity=2)

    # Assertions
    assert building.operational_components.count() == 2
    assert epd1 in building.operational_components.all()
    assert epd2 in building.operational_components.all()


@pytest.mark.django_db
def test_building_structural_components_assignment():
    # Create Assemblies
    assembly1 = Assembly.objects.create(name="Assembly 1")
    assembly2 = Assembly.objects.create(name="Assembly 2")

    # Create building
    building = Building.objects.create(
        name="Structural Building",
        climate_zone="Temperate",
        total_floor_area=Decimal("2000"),
        reference_period=50
    )

    # Assign structural components via through_defaults
    building.structural_components.add(
        assembly1,
        through_defaults={
            "quantity": Decimal("0"),
            "reporting_life_cycle": 50  # Provide required field
        }
    )
    building.structural_components.add(
        assembly2,
        through_defaults={
            "quantity": Decimal("0"),
            "reporting_life_cycle": 50
        }
    )

    # Assertions
    assert building.structural_components.count() == 2
    assert assembly1 in building.structural_components.all()
    assert assembly2 in building.structural_components.all()


@pytest.mark.django_db
def test_building_creation_minimal():
    # Minimal required fields
    building = Building.objects.create(
        name="Minimal Building",
        climate_zone="Tropical",
        total_floor_area=Decimal("500"),
        reference_period=30
    )

    assert building.name == "Minimal Building"
    assert building.total_floor_area == Decimal("500")
    assert building.reference_period == 30
