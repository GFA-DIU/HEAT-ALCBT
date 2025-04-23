from decimal import Decimal

import pytest

from pages.tests.test_impact_calculation import create_epd

from pages.models.epd import EPDImpact, Impact, ImpactCategoryKey, LifeCycleStage, Unit
from pages.models.building import OperationalProduct, Building, ClimateZone

from pages.views.building.impact_calculation import calculate_impact_operational


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
        return EPDImpact.objects.create(
            epd=epd,
            impact=impact,
            value=value,
        )

    return _create_epd_impact


@pytest.fixture
def create_building():
    def _create_building():
        return Building.objects.create(
            name="Test Building",
            climate_zone=ClimateZone.COLD,
            total_floor_area=1,
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

@pytest.mark.django_db
@pytest.mark.parametrize(
    "epd_name, declared_unit, conversions, epdimpact_value_gwp, epdimpact_value_penrt, product_quantity, product_unit, expected_impact_gwp, expected_impact_penrt",
    [
        ( # From Project 1__ LCA_14022024.xlsm
            "natural gas",                                                          # epd_name
            Unit.KWH,                                                               # declared_unit
            [{"unit": "kg/m^3", "value": "0.76"},{"unit": "kg", "value": "7.92"}],   # conversions
            Decimal("0.24"),                                                        # epdimpact value gwp
            Decimal("3.96"),                                                        # epdimpact value penrt
            Decimal("10"),                                                          # product_value
            Unit.M3,                                                                # product unit
            Decimal("14.4446208"),                                                  # expected impact gwp
            Decimal("238.3362432"),                                                 # expected impact penrt
        ),
        ( # From Project 1__ LCA_14022024.xlsm (own addition)
            "biogas",
            Unit.KWH,
            [{"unit": "kg/m^3", "value": "0.72"}, {"unit": "kg", "value": "9.03",}],
            Decimal("0.140"),
            Decimal("3.96"),
            Decimal("10"),
            Unit.LITER,
            Decimal("0.0091"),
            Decimal("0.2574"),
        ),
        ( # From Project 1__ LCA_14022024.xlsm (own addition)
            "wood pellets",
            Unit.KWH,
            [{"unit": "kg/m^3", "value": "650"}, {"unit": "kg", "value": "4.9",}],
            Decimal("0.03"),
            Decimal("0.72"),
            Decimal("10"),
            Unit.KG,
            Decimal("1.47"),
            Decimal("35.28"),
        ),
        ( # From Project 1__ LCA_14022024.xlsm (own addition)
            "coal",
            Unit.KWH,
            [{"unit": "kg/m^3", "value": "760"}, {"unit": "kg", "value": "8.14"}],
            Decimal("0.4"),
            Decimal("3.96"),  
            Decimal("10"),
            Unit.M3,
            Decimal("24745.6"),
            Decimal("244981.44"),
        ),
        ( # From Project 1__ LCA_14022024.xlsm (own addition)
            "bio oil",
            Unit.KWH,
            [{"unit": "kg/m^3", "value": "880"}, {"unit": "kg", "value": "11.53"}],
            Decimal("0.21"),
            Decimal("3.96"),
            Decimal("10"),
            Unit.LITER,
            Decimal("21.305103448275900"),
            Decimal("401.753379310345000"),
        ),
        ( # From Project 1__ LCA_14022024.xlsm (own addition)
            "electricity, geneated close to building",
            Unit.KWH,
            [],
            Decimal("0.56"),
            Decimal("6.48"),
            Decimal("10"),
            Unit.KWH,
            Decimal("5.6"),
            Decimal("64.8"),
        ),
    ],
)
def test_calculate_impact_operational(
    epd_name,
    declared_unit,
    conversions,
    epdimpact_value_gwp,
    epdimpact_value_penrt,
    product_quantity,
    product_unit,
    expected_impact_gwp,
    expected_impact_penrt,
    # Functions
    create_impact_B6,
    create_epd,
    create_epd_impact,
    create_operationalproduct,
    create_building,
):
    """Test if calculate impact matches Excel.
    
    Note:
     - Excel comparison implies `reporting_life_cycle=1` and `assembly_quantity=1`

    ARRANGE: Create simple Ökobaudat EPD and set to product from Excel.
    ACT: Calculate impact of product
    ASSERT: Matches expected values from Excel
    """
    # Arrange: Set up test data
    impact_gwp = create_impact_B6(ImpactCategoryKey.GWP)
    impact_penrt = create_impact_B6(ImpactCategoryKey.PENRT)
    epd = create_epd(epd_name, declared_unit, conversions)
    create_epd_impact(epd, epdimpact_value_gwp, impact_gwp)
    create_epd_impact(epd, epdimpact_value_penrt, impact_penrt)
    building = create_building()
    product = create_operationalproduct(building, epd, product_quantity, product_unit)
    
    rslt = calculate_impact_operational(product)
    
    assert rslt["gwp_b6"] == pytest.approx(
        expected_impact_gwp, rel=Decimal("1e-3")
    )
    assert rslt["penrt_b6"] == pytest.approx(
        expected_impact_penrt, rel=Decimal("1e-3")
    )
    

