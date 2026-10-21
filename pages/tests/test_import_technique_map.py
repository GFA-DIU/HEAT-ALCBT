"""The legacy construction-technique map.

Migration 0046 renamed and merged techniques alongside the categories. The
template still offers the old names: 42 of the 90 in its dropdown no longer
existed, and each one imported with classification = None in silence.

The map was built against the LIVE catalogue rather than from
docs/taxonomy_mapping.md, because the migration did not follow all of that
draft - see test_the_windows_prefixes_follow_the_catalogue below.
"""
import warnings

import openpyxl
import pytest

from pages.views.building.import_building import (
    _LEGACY_CATEGORY_NAMES, _LEGACY_TECHNIQUE_NAMES, _get_structural_category_map,
    _resolve_technique_name,
)

TEMPLATE = "static/docs/import-template.xlsx"
EM = "—"


# --- the map itself --------------------------------------------------------

def test_the_map_is_keyed_by_category():
    """The same old string means different things in different categories:
    "In-Situ Reinforced Concrete Slab" was renamed under Basement and kept
    under Roof. A flat name-to-name map would have broken Roof."""
    for key in _LEGACY_TECHNIQUE_NAMES:
        assert isinstance(key, tuple) and len(key) == 2, key
        category, old = key
        assert old == old.lower(), "lookup is lower-cased: %r" % (old,)


def test_the_two_merges_from_the_spec():
    """Both aluminium spellings fold into one technique - 83 combined uses on
    windows, 433 on doors."""
    assert _LEGACY_TECHNIQUE_NAMES[("Windows", "aluminium windows")] == \
        "Frame " + EM + " Aluminium"
    assert _LEGACY_TECHNIQUE_NAMES[("Windows", "aluminum")] == \
        "Frame " + EM + " Aluminium"
    assert _LEGACY_TECHNIQUE_NAMES[("Doors", "aluminium doors")] == "Aluminium"
    assert _LEGACY_TECHNIQUE_NAMES[("Doors", "aluminum")] == "Aluminium"


def test_the_windows_prefixes_follow_the_catalogue_not_the_spec():
    """docs/taxonomy_mapping.md proposed dropping the "Frame -" and
    "Glazing -" prefixes. The migration kept them. Mapping to the spec's names
    would have left all nine Windows techniques unresolved while looking
    right."""
    assert _LEGACY_TECHNIQUE_NAMES[("Windows", "single glazing")] == \
        "Glazing " + EM + " Single"
    assert _LEGACY_TECHNIQUE_NAMES[("Windows", "single glazing")] != "Single Glazing"


def test_the_air_gap_widths_merge():
    assert _LEGACY_TECHNIQUE_NAMES[("Insulation", "air gap <100mm wide")] == "Air Gap"
    assert _LEGACY_TECHNIQUE_NAMES[("Insulation", "air gap >100mm wide")] == "Air Gap"


@pytest.mark.parametrize("dropped,category", [
    ("Precast Concrete Sandwich Panel", "Internal Walls & Partitions"),
    ("Cement Fiber Boards on Timber Studs", "Internal Walls & Partitions"),
    ("Micro Concrete Tiles on Timber Rafters", "Roof"),
    ("Cellulose", "Insulation"),
    ("Re-use of Existing Window Frames", "Windows"),
])
def test_the_migrations_drops_are_not_mapped(dropped, category):
    """These were dropped with zero recorded uses. A row naming one imports
    without a classification rather than being refused: the material, quantity
    and carbon are all still good."""
    assert (category, dropped.lower()) not in _LEGACY_TECHNIQUE_NAMES


def test_a_name_that_needs_no_translation_passes_through():
    class _Cat:
        name = "Roof"
    assert _resolve_technique_name(_Cat(), "Concrete Filler Slab") == "Concrete Filler Slab"


def test_a_blank_or_missing_category_is_safe():
    assert _resolve_technique_name(None, "anything") == "anything"

    class _Cat:
        name = "Roof"
    assert _resolve_technique_name(_Cat(), "") == ""


# --- against the live catalogue --------------------------------------------

# The consolidated taxonomy is not created by a migration, so a bare "is the
# table empty" guard lets these pass on a database holding the PRE-0046 set -
# which is how a test ends up unable to fail. This name exists only after the
# consolidation, so its absence means the taxonomy to check is simply not here.
_SENTINEL = "Plain Cement Concrete (PCC) Footings"


def _require_consolidated_taxonomy():
    from pages.models.assembly import AssemblyTechnique

    if not AssemblyTechnique.objects.filter(name__iexact=_SENTINEL).exists():
        pytest.skip(
            "this database does not hold the consolidated (post-0046) "
            "taxonomy - %r is absent" % _SENTINEL)


@pytest.mark.django_db
def test_every_target_exists_and_belongs_to_its_category():
    """A target that is not LINKED to the category produces no classification
    even though the technique exists, so the name alone is not enough."""
    from pages.models.assembly import AssemblyCategoryTechnique

    _require_consolidated_taxonomy()

    links = {}
    for act in AssemblyCategoryTechnique.objects.select_related(
            "category", "technique"):
        # technique is null on each category's "Not specified" option.
        if act.category is None or act.technique is None:
            continue
        links.setdefault(act.category.name.lower(), set()).add(
            act.technique.name.lower())

    missing = [
        (category, old, new)
        for (category, old), new in _LEGACY_TECHNIQUE_NAMES.items()
        if new.lower() not in links.get(category.lower(), set())
    ]
    assert not missing, "targets not linked to their category: %s" % missing


@pytest.mark.django_db
def test_the_template_dropdown_resolves_except_the_drops():
    from pages.models.assembly import AssemblyTechnique

    _require_consolidated_taxonomy()
    known = {t.lower() for t in AssemblyTechnique.objects.values_list(
        "name", flat=True)}

    cat_map = _get_structural_category_map()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        wb = openpyxl.load_workbook(TEMPLATE, data_only=True)

    group, unresolved = None, set()
    for row in wb["List"].iter_rows(min_row=2, values_only=True):
        head = row[21] if len(row) > 21 else None
        name = row[22] if len(row) > 22 else None
        if head not in (None, "") and not str(head).strip().isdigit():
            group = str(head).strip()
        if name in (None, ""):
            continue
        category = cat_map.get((group or "").lower())
        resolved = _resolve_technique_name(category, str(name).strip())
        if resolved.lower() not in known:
            unresolved.add(str(name).strip())

    # Exactly the migration's deliberate drops, and nothing else.
    assert unresolved == {
        "Precast Concrete Double Tee Floor Units",
        "Precast Concrete Double Tee Roof Units",
        "Thin Precast Concrete Deck and Composite In-situ Slab",
        "Micro Concrete Tiles on Timber Rafters",
        "Precast Concrete Sandwich Panel",
        "Cement Fiber Boards on Timber Studs",
        "Plasterboards on Timber Studs with Insulation",
        "Plasterboards on Metal Studs with Insulation",
        "Aluminum Clad Timber",
        "Re-use of Existing Window Frames",
        "Cellulose",
    }, sorted(unresolved)


@pytest.mark.django_db
def test_the_templates_own_example_technique_resolves():
    """"Stones and Tiles" is on the shipped example row and did not exist."""
    from pages.models.assembly import AssemblyTechnique

    _require_consolidated_taxonomy()

    cat_map = _get_structural_category_map()
    category = cat_map.get("floor finish")
    assert category is not None and category.name == "Finishes"
    resolved = _resolve_technique_name(category, "Stones and Tiles")
    assert AssemblyTechnique.objects.filter(name__iexact=resolved).exists()


def test_every_legacy_category_is_a_real_target():
    """The technique map is keyed on NEW category names, so each one must be
    something _LEGACY_CATEGORY_NAMES actually produces or already is."""
    produced = set(_LEGACY_CATEGORY_NAMES.values()) | {
        "Foundations", "Columns", "Roof", "Windows", "Doors", "Finishes",
        "Insulation", "Miscellaneous", "Beams & Slabs", "Ground Floor",
        "External Walls", "Internal Walls & Partitions",
        "Staircases & Ramps", "Basement & Retaining Walls",
    }
    for category, _ in _LEGACY_TECHNIQUE_NAMES:
        assert category in produced, category


# --- deterministic, independent of what the database happens to hold --------

@pytest.mark.django_db
def test_resolution_against_a_seeded_catalogue():
    """The checks above skip where the consolidated taxonomy is absent, so
    this one seeds exactly what the map points at and proves the lookup path
    end to end."""
    from pages.models.assembly import (
        AssemblyCategory, AssemblyCategoryTechnique, AssemblyTechnique,
    )

    for (category_name, _), target in _LEGACY_TECHNIQUE_NAMES.items():
        category, _ = AssemblyCategory.objects.get_or_create(name=category_name)
        technique, _ = AssemblyTechnique.objects.get_or_create(name=target)
        AssemblyCategoryTechnique.objects.get_or_create(
            category=category, technique=technique)

    for (category_name, old), target in _LEGACY_TECHNIQUE_NAMES.items():
        category = AssemblyCategory.objects.get(name=category_name)
        resolved = _resolve_technique_name(category, old)
        assert resolved == target
        assert AssemblyTechnique.objects.filter(name__iexact=resolved).exists()
        assert AssemblyCategoryTechnique.objects.filter(
            category=category, technique__name__iexact=resolved,
        ).exists(), "%s / %s is not linked" % (category_name, resolved)


@pytest.mark.django_db
def test_the_same_old_name_resolves_differently_per_category():
    """"Aluminum" is a frame under Windows and a door leaf under Doors."""
    from pages.models.assembly import AssemblyCategory

    windows, _ = AssemblyCategory.objects.get_or_create(name="Windows")
    doors, _ = AssemblyCategory.objects.get_or_create(name="Doors")
    assert _resolve_technique_name(windows, "Aluminum") == "Frame " + EM + " Aluminium"
    assert _resolve_technique_name(doors, "Aluminum") == "Aluminium"
