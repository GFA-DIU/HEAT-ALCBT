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


@pytest.mark.parametrize("value, expected", [
    ("5", 5), ("  7 ", 7), ("TH", None), ("abc", None),
    ("", None), (None, None), ("0", None), ("-3", None),
])
def test_filter_values_that_are_not_ids_are_dropped_not_fatal(value, expected):
    """`country=TH` used to reach the ORM and return a 500.

    ValueError: Field 'id' expected a number but got 'TH'. A stale bookmark or
    a hand-edited URL should show no results, not an error page.
    """
    from pages.views.assembly.epd_filtering import _as_pk
    assert _as_pk(value) == expected


# --- the maker is not said twice -------------------------------------------
#
# 48 of 284 India EPDs name their maker inside the title already, so appending
# manufacturer produced "Hardtop XP II, Jotun India Private Limited - Jotun
# A/S". Suppressing it must not go so far as to hide a DIFFERENT company whose
# name merely starts with the same word.

def test_display_name_omits_a_maker_the_title_already_names(epd):
    epd.material_name = "Hardtop XP II, Jotun India Private Limited"
    epd.product_name = None
    epd.manufacturer = "Jotun A/S"
    assert epd.display_name == "Hardtop XP II, Jotun India Private Limited"


def test_display_name_omits_a_maker_the_product_already_names(epd):
    epd.material_name = "Furniture"
    epd.product_name = "Ikkita Chair-Alankaram"
    epd.manufacturer = "Alankaram"
    assert epd.display_name == "Furniture - Ikkita Chair-Alankaram"


def test_display_name_keeps_a_maker_that_only_shares_a_word(epd):
    """"Steel Authority of India" is not "Steel sheet". Matching on the first
    word alone would drop the maker here."""
    epd.material_name = "Steel sheet"
    epd.product_name = None
    epd.manufacturer = "Steel Authority of India Limited"
    assert epd.display_name == "Steel sheet - Steel Authority of India Limited"


def test_display_name_still_appends_a_maker_not_otherwise_named(epd):
    epd.material_name = "Portland Slag Cement (PSC)"
    epd.product_name = None
    epd.manufacturer = "UltraTech Cement Ltd."
    assert epd.display_name == "Portland Slag Cement (PSC) - UltraTech Cement Ltd."


def test_display_name_names_the_maker_even_without_a_material(epd):
    """Nine records are titled "Xtend" or "Stonix" and have no material_name.
    Returning early hid the maker, which was the only identifying detail they
    had."""
    epd.material_name = None
    epd.product_name = None
    epd.name = "Xtend"
    epd.manufacturer = "Greenex Environmental"
    assert epd.display_name == "Xtend - Greenex Environmental"


def test_display_name_without_a_material_or_maker_is_unchanged(epd):
    epd.material_name = None
    epd.product_name = None
    epd.manufacturer = None
    epd.name = "Xtend"
    assert epd.display_name == "Xtend"


def test_display_name_omits_a_maker_the_brand_prefix_already_names(epd):
    """The four UltraTech cement records carry the brand in their title. The
    maker must not then be repeated as a suffix."""
    epd.material_name = "UltraTech Portland Slag Cement (PSC)"
    epd.product_name = None
    epd.manufacturer = "UltraTech Cement Ltd."
    assert epd.display_name == "UltraTech Portland Slag Cement (PSC)"
