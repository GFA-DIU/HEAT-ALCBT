from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError

from pages.models.epd import Unit
from pages.models.assembly import Assembly, AssemblyMode, AssemblyDimension
from pages.views.building.impact_calculation import calculate_impacts

from pages.tests.test_impact_calculation import (
    create_epd,
    create_impact,
    create_epd_impact,
    create_assembly,
    create_product,
)


@pytest.fixture
def create_boq_assembly():
    def _create_assembly():
        return Assembly.objects.create(
            mode=AssemblyMode.CUSTOM,
            dimension=AssemblyDimension.AREA,
            is_boq=True
        )

    return _create_assembly


@pytest.mark.django_db
@pytest.mark.parametrize(
    "epd_name, declared_unit, conversions, epdimpact_value, product_quantity, product_unit, expected_impact",
    [
        ( # Test Pieces
            "Test PCS",                                  # epd_name
            Unit.PCS,                                    # declared_unit
            [],                                          # conversions
            Decimal("3"),                                # epdimpact value
            Decimal("4"),                                # product_quantity
            Unit.PCS,                                    # product unit  
            Decimal("12"),   # 3 * 4                     # expected impact
        ),
        ( # Test M
            "Test M",
            Unit.M,
            [{"unit": "kg/m^3", "value": "2"}, {"unit": "kg/m", "value": "300"}],
            Decimal("3"),
            Decimal("4"),
            Unit.M,
            Decimal("12"),  # 3 * 4
        ),
        ( # Test M2
            "Test M2",
            Unit.M2,
            [{"unit": "kg/m^3", "value": "2"}, {"unit": "kg/m", "value": "300"}],
            Decimal("3"),
            Decimal("4"),
            Unit.M2,
            Decimal("12"),  # 3 * 4
        ),
        ( # Test M3
            "Test M3",
            Unit.M3,
            [{"unit": "kg/m^3", "value": "2"}, {"unit": "kg/m", "value": "300"}],
            Decimal("3"),
            Decimal("4"),
            Unit.M3,
            Decimal("12"),  # 3 * 4
        ),
        ( # Test KG
            "Test KG",
            Unit.KG,
            [{"unit": "kg/m^3", "value": "2"}, {"unit": "kg/m", "value": "300"}],
            Decimal("3"),
            Decimal("4"),
            Unit.KG,
            Decimal("12"),  # 3 * 4
        ),
    ],
)
def test_calculate_impacts_boq(
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
    create_boq_assembly,
    create_product,
):
    """Test if calculate impact works for BoQs.
    
    In BoQs the assembly Dimension plays no role. Currently conversions are not touched.

    ARRANGE: Create simple EPD and Product for an assembly with is_boq=True
    ACT: Calculate impact of product.
    ASSERT: Matches expected values.
    """
    #TODO if conversions are used for BoQs, extend test.
    # Arrange: Set up test data
    impact = create_impact
    epd = create_epd(epd_name, declared_unit, conversions)
    create_epd_impact(epd, epdimpact_value)
    assembly = create_boq_assembly()
    product = create_product(assembly, epd, product_quantity, product_unit)

    # Act: Perform the calculation
    impacts = calculate_impacts(
        dimension=None,
        assembly_quantity=1,
        total_floor_area=1,
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
    "epd_name, declared_unit, conversions, epdimpact_value, product_quantity, product_unit",
    [
        ( # conversions are not used
            "Test M3",
            Unit.M3,
            [{"unit": "kg/m^3", "value": "2"}, {"unit": "kg/m^2", "value": "20"}],
            Decimal("3"),
            Decimal("4"),
            Unit.KG,
        ),
        ( # conversions are not used
            "Test KG",
            Unit.KG,
            [{"unit": "kg/m^3", "value": "2"}, {"unit": "kg/m^2", "value": "20"}],
            Decimal("3"),
            Decimal("4"),
            Unit.M3,
        ),
    ],
)
def test_calculate_impacts_boq_errors(
    epd_name,
    declared_unit,
    conversions,
    epdimpact_value,
    product_quantity,
    product_unit,
    ### Functions
    create_epd,
    create_epd_impact,
    create_boq_assembly,
    create_product,
):
    """Test if calculate impact satisfies dimension logic.
    
    Note
     - currently BoQs do not use conversions.

    ARRANGE: Create simple EPD and set input unit for matching conversion.
    ACT: Create product.
    ASSERT: Raises validation error.
    """

    # Arrange: Set up test data
    epd = create_epd(epd_name, declared_unit, conversions)
    create_epd_impact(epd, epdimpact_value)
    assembly = create_boq_assembly()
    
    product = create_product(assembly, epd, product_quantity, product_unit)
    
    assert product is not None
