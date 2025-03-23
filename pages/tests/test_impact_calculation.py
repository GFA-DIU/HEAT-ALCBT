from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError

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
    def _create_assembly(dimension):
        return Assembly.objects.create(
            mode=AssemblyMode.CUSTOM,
            dimension=dimension,
        )

    return _create_assembly


@pytest.fixture
def create_product():
    def _create_product(assembly, epd, quantity, unit):
        assemblycategorytechnique = AssemblyCategoryTechnique.objects.create(
            category=AssemblyCategory.objects.first(),
            technique=AssemblyTechnique.objects.first(),
            description="Created for test",
        )
        return Product.objects.create(
            assembly=assembly,
            epd=epd,
            quantity=quantity,
            input_unit=unit,
            classification=assemblycategorytechnique
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
def test_calculate_impacts_area_assembly_benchmark(
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
    """Test if calculate impact matches Excel calculation of area assembly.
    
    Note:
     - Excel comparison implies `reporting_life_cycle=1` and `assembly_quantity=1`

    ARRANGE: Create simple Ökobaudat EPD and set to product from Excel with an area assembly.
    ACT: Calculate impact of product
    ASSERT: Matches expected values from Excel
    """

    # Arrange: Set up test data
    impact = create_impact
    epd = create_epd(epd_name, declared_unit, conversions)
    create_epd_impact(epd, epdimpact_value)
    assembly = create_assembly(dimension=AssemblyDimension.AREA)
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


# Parametrized test with fixtures
@pytest.mark.django_db
@pytest.mark.parametrize(
    "epd_name, declared_unit, conversions, epdimpact_value, product_quantity, product_unit, dimension, expected_impact",
    [
        ( # Ensure kg/m^3 is used for KG conversion
            "Test KG with M^2 & M^3",                                                   # epd_name
            Unit.KG,                                                                    # declared_unit
            [{"unit": "kg/m^3", "value": "2"}, {"unit": "kg/m^2", "value": "300"}],     # conversions
            Decimal("3"),                                                               # epdimpact value
            Decimal("4"),                                                               # product_quantity
            Unit.CM,                                                                    # product unit  
            AssemblyDimension.AREA,                                                     # dimension
            Decimal("0.24"),   # 3 * 4 * 2 / 100                                        # expected impact
        ),
        ( # Ensure kg/m^3 is prioritized for KG conversion
            "Test KG with M & M^3",
            Unit.KG,
            [{"unit": "kg/m^3", "value": "2"}, {"unit": "kg/m", "value": "300"}],
            Decimal("3"),
            Decimal("4"),
            Unit.CM2,
            AssemblyDimension.LENGTH,
            Decimal("0.0024"),  # 3 * 4 * 2 / 1000
        ),
        ( # Ensure KG fallback to m^3 works
            "Test KG with M^3",
            Unit.KG,
            [{"unit": "kg/m^3", "value": "2"}],
            Decimal("3"),
            Decimal("4"),
            Unit.CM2,
            AssemblyDimension.LENGTH,
            Decimal("0.0024"),  # 3 * 4 * 2 / 1000
        ),
        ( # Ensure M3 conversion for Volume Dimension
            "Test M3 for Mass",
            Unit.M3,
            [{"unit": "kg/m^3", "value": "2"}, {"unit": "kg/m^2", "value": "300"}],
            Decimal("3"),
            Decimal("4"),
            Unit.PERCENT,
            AssemblyDimension.MASS,
            Decimal("0.06"),  # 3 * 4 / 2 / 100 (because percent)
        ),
        ( # Ensure for PCS Dimension
            "Test PCS",
            Unit.PCS,
            [{"unit": "kg/m^3", "value": "8"}, {"unit": "kg/m^2", "value": "300"}],
            Decimal("3"),
            Decimal("4"),
            Unit.PCS,
            AssemblyDimension.MASS,
            Decimal("12"),  # 3 * 4
        ),
    ],
)
def test_calculate_impacts_dimension_logic(
    epd_name,
    declared_unit,
    conversions,
    epdimpact_value,
    product_quantity,
    product_unit,
    dimension,
    expected_impact,
    ### Functions
    create_impact,
    create_epd,
    create_epd_impact,
    create_assembly,
    create_product,
):
    """Test if calculate impact satisfies dimension logic.
    
    # Note:
     - KG needs special consideration since these are scaled

    ARRANGE: Create simple EPD and set dimension of assembly.
    ACT: Calculate impact of product.
    ASSERT: Matches expected value.
    """

    # Arrange: Set up test data
    impact = create_impact
    epd = create_epd(epd_name, declared_unit, conversions)
    create_epd_impact(epd, epdimpact_value)
    assembly = create_assembly(dimension=dimension)
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



# Parametrized test with fixtures
@pytest.mark.django_db
@pytest.mark.parametrize(
    "epd_name, declared_unit, conversions, epdimpact_value, product_quantity, product_unit, dimension, expected_impact",
    [
        ( # Ensure KG conversion for Volume Dimension
            #TODO changed dimension to KG
            "Test M3 for Mass",
            Unit.M3,
            [{"unit": "kg/m^3", "value": "2"}, {"unit": "kg/m^2", "value": "20"}],
            Decimal("3"),
            Decimal("4"),
            Unit.CM,
            AssemblyDimension.MASS,
            Decimal("0.6"),
        ),
        ( # Ensure KG fallback to m works
            "Test KG with M",
            Unit.KG,
            [{"unit": "kg/m", "value": "2"}],
            Decimal("3"),
            Decimal("4"),
            Unit.UNKNOWN,
            AssemblyDimension.LENGTH,
            Decimal("0.6"),
        ),
        ( # Ensure KG fallback to m^2 works
            "Test KG with M^2",
            Unit.KG,
            [{"unit": "kg/m^2", "value": "2"}],
            Decimal("3"),
            Decimal("4"),
            Unit.UNKNOWN,
            AssemblyDimension.AREA,
            Decimal("0.6"),
        ),
    ],
)
def test_calculate_impacts_errors(
    epd_name,
    declared_unit,
    conversions,
    epdimpact_value,
    product_quantity,
    product_unit,
    dimension,
    expected_impact,
    ### Functions
    create_impact,
    create_epd,
    create_epd_impact,
    create_assembly,
    create_product,
):
    """Test if calculate impact satisfies dimension logic.

    ARRANGE: Create simple EPD and set dimension of assembly.
    ACT: Calculate impact of product.
    ASSERT: Matches expected value.
    """

    # Arrange: Set up test data
    impact = create_impact
    epd = create_epd(epd_name, declared_unit, conversions)
    create_epd_impact(epd, epdimpact_value)
    assembly = create_assembly(dimension=dimension)
    
    with pytest.raises(ValidationError):
        product = create_product(assembly, epd, product_quantity, product_unit)

        # # Act: Perform the calculation
        # impacts = calculate_impacts(
        #     dimension=assembly.dimension,
        #     assembly_quantity=1,
        #     reporting_life_cycle=1,
        #     p=product,
        # )
