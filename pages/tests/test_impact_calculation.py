from decimal import Decimal

import pytest

from pages.models.assembly import (
    Assembly,
    AssemblyCategory,
    AssemblyCategoryTechnique,
    AssemblyDimension,
    AssemblyMode,
    AssemblyTechnique,
    Product,
)
from pages.models.epd import (
    EPD,
    EPDImpact,
    EPDType,
    Impact,
    ImpactCategoryKey,
    LifeCycleStage,
    MaterialCategory,
    Unit,
)
from pages.views.building.impact_calculation import calculate_impacts


# Fixtures for reusable components
@pytest.fixture
def create_impact():
    return Impact.objects.create(
        impact_category=ImpactCategoryKey.GWP,
        life_cycle_stage=LifeCycleStage.A1A3,
        unit=Unit.KGCO2E,
    )


@pytest.fixture
def create_epd():
    def _create_epd(name, declared_unit, conversions):
        return EPD.objects.create(
            names=[{"value": name, "lang": "en"}],
            type=EPDType.CUSTOM,
            declared_amount=1,
            category=MaterialCategory.objects.first(),
            declared_unit=declared_unit,
            conversions=conversions,
        )

    return _create_epd


@pytest.fixture
def create_epd_impact(create_impact):
    def _create_epd_impact(epd, value):
        return EPDImpact.objects.create(
            epd=epd,
            impact=create_impact,
            value=value,
        )

    return _create_epd_impact


@pytest.fixture
def create_assembly():
    def _create_assembly():
        assemblycategorytechnique = AssemblyCategoryTechnique.objects.create(
            category=AssemblyCategory.objects.first(),
            technique=AssemblyTechnique.objects.first(),
            description="Created for test",
        )
        return Assembly.objects.create(
            mode=AssemblyMode.CUSTOM,
            dimension=AssemblyDimension.AREA,
            classification=assemblycategorytechnique,
        )

    return _create_assembly


@pytest.fixture
def create_product():
    def _create_product(assembly, epd, quantity, unit):
        return Product.objects.create(
            assembly=assembly,
            epd=epd,
            quantity=quantity,
            input_unit=unit,
        )

    return _create_product


# Parametrized test with fixtures
@pytest.mark.django_db
@pytest.mark.parametrize(
    "epd_name, declared_unit, conversions, epdimpact_value, product_quantity, product_unit, expected_impact",
    [
        ( # From Excel: 2024-12-18 - LCA modelling - phase II - with macro.xlsm
            "Cement screed",                        # epd_name
            Unit.KG,                                # declared_unit
            [{"unit": "kg/m^3", "value": "2200"}],  # conversions
            Decimal("0.183550838458225"),           # epdimpact value
            Decimal("3.5"),                         # product_value
            Unit.CM,                                # product unit                          # assembly_quantity
            Decimal("14.1334145612833"),            # expected impact
        ),
        ( # From Excel `2024-12-18 - LCA modelling - phase II - with macro.xlsm`
            "PE foil, dimpled",
            Unit.M2,
            [{"unit": "kg/m^3", "value": "100"}],  # is not supposed to matter
            Decimal("4.12"),
            Decimal("1"),
            Unit.UNKNOWN,
            Decimal("4.12"),
        ),
        ( # Ensure M2 conversions doesn't matter for result
            "PE foil, dimpled",
            Unit.M2,
            [],
            Decimal("4.12"),
            Decimal("1"),
            Unit.UNKNOWN,
            Decimal("4.12"),
        ),
        ( # From Excel `2024-12-18 - LCA modelling - phase II - with macro.xlsm`
            "Extruded Polystrene (XPS)",
            Unit.M3,
            [{"unit": "kg/m^3", "value": "32"}],
            Decimal("94.0282964318439"),
            Decimal("5"),
            Unit.CM,
            Decimal("4.70141482159219"),
        ),
        ( # Ensure M3 conversion doesn't matter for result
            "Extruded Polystrene (XPS)",
            Unit.M3,
            [{"unit": "kg/m^3", "value": "100"}],
            Decimal("94.0282964318439"),
            Decimal("5"),
            Unit.CM,
            Decimal("4.70141482159219"),
        ),
    ],
)
def test_calculate_impacts_area(
    epd_name,
    declared_unit,
    conversions,
    epdimpact_value,
    product_quantity,
    product_unit,
    expected_impact,
    ### Functions
    create_impact,
    create_epd,
    create_epd_impact,
    create_assembly,
    create_product,
):
    """Test if calculate impact matches Excel.
    
    Note:
     - Excel comparison implies `reporting_life_cycle=1` and `assembly_quantity=1`

    ARRANGE: Create simple Ökobaudat EPD and set to product from Excel.
    ACT: Calculate impact of product
    ASSERT: Matches expected values from Excel
    """

    # Arrange: Set up test data
    impact = create_impact
    epd = create_epd(epd_name, declared_unit, conversions)
    create_epd_impact(epd, epdimpact_value)
    assembly = create_assembly()
    product = create_product(assembly, epd, product_quantity, product_unit)

    # Act: Perform the calculation
    impacts = calculate_impacts(
        dimension=assembly.dimension,
        assembly_quantity=1,
        reporting_life_cycle=1,
        p=product,
    )

    # Assert: Verify the results
    assert len(impacts) == 1
    for impact in impacts:
        assert impact["impact_type"].__str__() == "gwp a1a3"
        assert isinstance(impact["impact_value"], Decimal)
        assert impact["impact_value"] == pytest.approx(
            expected_impact, rel=Decimal("1e-15")
        )
