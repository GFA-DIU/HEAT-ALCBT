import pytest


from pages.models.assembly import AssemblyDimension
from pages.models.epd import EPD, Unit
from pages.tests.test_impact_calculation import create_epd

from pages.views.assembly.epd_filtering import filter_by_dimension


@pytest.mark.django_db
@pytest.mark.parametrize(
    "declared_unit, conversions, dimension, expect_match",
    [
        # PCS EPDs
        (Unit.PCS, [], AssemblyDimension.AREA, True),
        (Unit.PCS, [], AssemblyDimension.LENGTH, True),
        (Unit.PCS, [], AssemblyDimension.MASS, True),
        (Unit.PCS, [], AssemblyDimension.VOLUME, True),
        # M2 EPDs
        (Unit.M2, [], AssemblyDimension.AREA, True),
        (Unit.M2, [], AssemblyDimension.LENGTH, False),
        (Unit.M2, [], AssemblyDimension.MASS, False),
        (Unit.M2, [], AssemblyDimension.VOLUME, False),
        # M EPDs
        (Unit.M, [], AssemblyDimension.AREA, False),
        (Unit.M, [], AssemblyDimension.LENGTH, True),
        (Unit.M, [], AssemblyDimension.MASS, False),
        (Unit.M, [], AssemblyDimension.VOLUME, False),
        # KG EPDs - without conversion
        (Unit.KG, [], AssemblyDimension.AREA, False),
        (Unit.KG, [], AssemblyDimension.LENGTH, False),
        (Unit.KG, [], AssemblyDimension.MASS, True),
        (Unit.KG, [], AssemblyDimension.VOLUME, False),
        # KG EPDs - with conversion
        (Unit.KG, [{"unit": "kg/m^3"}], AssemblyDimension.AREA, True),
        (Unit.KG, [{"unit": "kg/m^2"}], AssemblyDimension.AREA, False),
        (Unit.KG, [{"unit": "kg/m^3"}], AssemblyDimension.LENGTH, True),
        (Unit.KG, [{"unit": "kg/m"}], AssemblyDimension.LENGTH, False),
        (Unit.KG, [{"unit": "kg/m^3"}], AssemblyDimension.MASS, True),
        (Unit.KG, [{"unit": "kg/m^3"}], AssemblyDimension.VOLUME, True),
        # M3 EPDs
        (Unit.M3, [], AssemblyDimension.AREA, True),
        (Unit.M3, [], AssemblyDimension.LENGTH, True),
        (Unit.M3, [], AssemblyDimension.MASS, False),
        (Unit.M3, [{"unit": "kg/m^3"}], AssemblyDimension.MASS, True),
        (Unit.M3, [], AssemblyDimension.VOLUME, True),
    ],
)
def test_filter_by_dimension(
    declared_unit, conversions, dimension, expect_match, create_epd
):
    """Check if EPDs are correctly filtered by dimension.
    
    In particular, check that KG is limited Mass if it does not have gross density.    
    
    ARRANGE: Create EPD with declared unit and optional conversions. Exclude rest of DB.
    ACT: Filter by the defined dimension
    ASSERT: Check if Queryset is empty or contains the epd.
    """

    # Arrange
    test_epd = create_epd("Test EPD", declared_unit, conversions)
    filtered_epds = EPD.objects.filter(id=test_epd.id)

    # Act
    rslt = filter_by_dimension(filtered_epds, dimension)

    # Assert
    if expect_match:
        assert list(rslt) == [test_epd]
    else:
        assert list(rslt) == []
