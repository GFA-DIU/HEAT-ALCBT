"""The composed EPD label has to survive the trip to the template.

The material picker does not hand EPD model instances to its template - it
builds a FilteredEPD dataclass with a fixed field list. A template referencing
an attribute that dataclass does not carry renders an empty string rather than
raising, so when display_name was added to the templates but not to
FilteredEPD, every product name in the picker silently vanished and only the
category badge was left. Nothing failed; the list just went blank.

These tests pin the two halves of that: the model composes the label, and the
view layer actually carries it through.
"""
import pytest

from pages.models.assembly import AssemblyDimension
from pages.models.epd import EPD, EPDType, MaterialCategory, Unit
from pages.views.assembly.epd_processing import LazyProcessor, prefetch_epds


@pytest.fixture
def epd(db):
    return EPD.objects.create(
        names=[{"value": "MU-307", "lang": "en"}],
        type=EPDType.CUSTOM,
        declared_amount=1,
        category=MaterialCategory.objects.first(),
        declared_unit=Unit.KG,
        conversions=[],
    )


@pytest.mark.django_db
def test_display_name_composes_material_product_maker(epd):
    epd.material_name = "Dry-mix mortar"
    epd.product_name = "MU-307"
    epd.manufacturer = "PT Cipta Mortar Utama"
    assert epd.display_name == "Dry-mix mortar - MU-307 - PT Cipta Mortar Utama"


@pytest.mark.django_db
def test_display_name_omits_a_material_that_only_repeats_the_category(epd):
    """The picker prints the category as a badge; the name must not stutter."""
    epd.material_name = epd.category.name_en
    epd.product_name = "Shotcrete"
    assert epd.display_name == "Shotcrete"


@pytest.mark.django_db
def test_display_name_falls_back_to_name(epd):
    """An EPD the backfill could not place must still show something."""
    epd.material_name = None
    assert epd.display_name == epd.name


@pytest.mark.django_db
def test_display_name_does_not_repeat_the_maker(epd):
    """Penetron is both the product and the company; say it once."""
    epd.material_name = "Concrete waterproofing admixture"
    epd.product_name = "Penetron"
    epd.manufacturer = "Penetron"
    assert epd.display_name == "Concrete waterproofing admixture - Penetron"


@pytest.mark.django_db
def test_picker_carries_display_name_through_to_the_template(epd):
    """The regression: FilteredEPD must expose display_name, not drop it."""
    epd.material_name = "Dry-mix mortar"
    epd.product_name = "MU-307"
    epd.save()

    qs = prefetch_epds(EPD.objects.filter(pk=epd.pk))
    items = LazyProcessor(qs, AssemblyDimension.MASS, operational=False)[0:1]

    assert items, "the picker returned no rows for the EPD under test"
    assert hasattr(items[0], "display_name"), (
        "FilteredEPD dropped display_name - the picker will render blank names"
    )
    assert items[0].display_name == "Dry-mix mortar - MU-307"
