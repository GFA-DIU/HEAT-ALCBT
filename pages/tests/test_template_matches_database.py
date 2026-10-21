"""Values the import template offers that the database no longer accepts.

Every one of these was a hard failure for the user: the row was rejected with
a message naming a value the template itself had just offered them.
"""
import warnings

import openpyxl
import pytest

from pages.views.building.import_building import (
    _LEGACY_CATEGORY_NAMES, _get_structural_category_map, _resolve_building_type,
)

TEMPLATE = "static/docs/import-template.xlsx"


def _list_column(index):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        wb = openpyxl.load_workbook(TEMPLATE, data_only=True)
    out = []
    for row in wb["List"].iter_rows(min_row=2, values_only=True):
        v = row[index] if len(row) > index else None
        if v not in (None, ""):
            out.append(str(v).strip())
    return out


# --- the Office grades -----------------------------------------------------

def test_the_template_no_longer_says_grade_a_office():
    """It offered "Office - grade A office" while the database stores the
    subcategory as "Grade A", so all three Office grades failed and no office
    building could be imported at all. The other 39 types were fine."""
    offices = [t for t in _list_column(1) if t.lower().startswith("office")]
    assert len(offices) == 3
    for t in offices:
        assert "office" not in t.split("–")[-1].lower(), t


@pytest.fixture
def office_types(db):
    from pages.models.building import (
        BuildingCategory, BuildingSubcategory, CategorySubcategory,
    )
    # Migrations already seed these, so take what is there rather than
    # colliding with it.
    cat, _ = BuildingCategory.objects.get_or_create(name="Office")
    for g in ("Grade A", "Grade B", "Grade C"):
        sub, _ = BuildingSubcategory.objects.get_or_create(name=g)
        CategorySubcategory.objects.get_or_create(category=cat, subcategory=sub)
    return cat


@pytest.mark.django_db
def test_the_corrected_wording_resolves(office_types):
    cs, err = _resolve_building_type("Office – Grade A")
    assert cs is not None, err
    assert cs.subcategory.name == "Grade A"


@pytest.mark.django_db
def test_the_old_wording_still_resolves(office_types):
    """Files saved from the old template, and anyone who typed the wording it
    showed them, still carry "grade A office"."""
    cs, err = _resolve_building_type("Office – grade A office")
    assert cs is not None, err
    assert cs.subcategory.name == "Grade A"


@pytest.mark.django_db
def test_only_the_categorys_own_word_is_stripped(office_types):
    """The tolerance must not turn into loose matching on anything."""
    cs, err = _resolve_building_type("Office – Grade Z")
    assert cs is None
    cs, err = _resolve_building_type("Office – Grade A warehouse")
    assert cs is None


# --- the consolidated component taxonomy -----------------------------------

@pytest.fixture
def categories(db):
    """The 14 categories migration 0046 left behind."""
    from pages.models.assembly import AssemblyCategory
    names = [
        "Foundations", "Basement & Retaining Walls", "Columns", "Beams & Slabs",
        "Ground Floor", "Roof", "Staircases & Ramps", "External Walls",
        "Internal Walls & Partitions", "Windows", "Doors", "Finishes",
        "Insulation", "Miscellaneous",
    ]
    for n in names:
        AssemblyCategory.objects.get_or_create(name=n)
    return names


@pytest.mark.django_db
def test_every_legacy_name_maps_to_a_real_category(categories):
    """Migration 0046 consolidated 19 components into 14 and is live on qa,
    but the template still names the old ones - and so does every file anyone
    saved from it."""
    cat_map = _get_structural_category_map()
    for old, new in _LEGACY_CATEGORY_NAMES.items():
        assert old in cat_map, f"{old!r} does not resolve"
        assert cat_map[old].name == new, f"{old!r} -> {cat_map[old].name!r}, want {new!r}"


@pytest.mark.django_db
def test_the_names_that_broke_the_templates_own_rows(categories):
    """11 of the template's 13 example structural rows named a category that
    no longer exists. Only Foundation and Columns still resolved."""
    cat_map = _get_structural_category_map()
    assert cat_map["bottom floor construction"].name == "Ground Floor"
    assert cat_map["intermediate floor construction"].name == "Beams & Slabs"
    assert cat_map["beams"].name == "Beams & Slabs"
    assert cat_map["roof construction"].name == "Roof"
    assert cat_map["floor finish"].name == "Finishes"
    assert cat_map["exterior walls"].name == "External Walls"


@pytest.mark.django_db
def test_a_current_name_is_never_shadowed_by_a_legacy_one(categories):
    """Current names win, so renaming a category back would not be masked."""
    cat_map = _get_structural_category_map()
    for n in categories:
        assert cat_map[n.lower()].name == n


@pytest.mark.django_db
def test_every_component_the_template_offers_resolves(categories):
    cat_map = _get_structural_category_map()
    units = {"units", "kg", "ton", "m", "pcs", "m²", "m³"}
    offered = [c for c in _list_column(8) if c.lower() not in units]
    missing = [c for c in offered if c.lower() not in cat_map]
    assert not missing, f"template offers components the database rejects: {missing}"
