"""
Consolidate the assembly taxonomy (building components + construction techniques).

Spec: docs/taxonomy_mapping.md   (19 categories -> 14, techniques cleaned/merged).

Design notes:
- The ONLY link from user data to the taxonomy is
  StructuralProduct.classification -> AssemblyCategoryTechnique (a category+technique join).
- We NEVER rename technique rows in place (names are globally unique and shared across
  categories). Instead we get_or_create destination rows BY NEW NAME, repoint every
  material's `classification` from its old join to the new one, then delete what's left.
- Techniques marked DROP must have zero materials (asserted). Only 0-use options are dropped.
- Category `tag` is reset to a zero-padded sort key so the dropdown lists components
  ground-up (Substructure -> Structure -> Envelope -> Finishes). The UI shows only the
  name (see assembly_form.py); tag is just an ordering key + admin label.
"""
from django.db import migrations

DROP = "__DROP__"

# new category name -> sort tag (lexicographic == ground-up order)
NEW_CATEGORIES = [
    ("Foundations", "010"),
    ("Basement & Retaining Walls", "020"),
    ("Columns", "030"),
    ("Beams & Slabs", "040"),
    ("Ground Floor", "050"),
    ("Roof", "060"),
    ("Staircases & Ramps", "070"),
    ("External Walls", "080"),
    ("Internal Walls & Partitions", "090"),
    ("Windows", "100"),
    ("Doors", "110"),
    ("Finishes", "120"),
    ("Insulation", "130"),
    ("Miscellaneous", "140"),
]
NEW_CATEGORY_TAGS = dict(NEW_CATEGORIES)
NEW_CATEGORY_NAMES = set(NEW_CATEGORY_TAGS)

# old category name -> new category name
CATEGORY_MAP = {
    "Foundation": "Foundations",
    "Basement": "Basement & Retaining Walls",
    "Columns": "Columns",
    "Beams, Slabs": "Beams & Slabs",
    "Intermediate Floor Construction": "Beams & Slabs",
    "Bottom Floor Construction": "Ground Floor",
    "Roof Construction": "Roof",
    "Staircases and Ramps": "Staircases & Ramps",
    "Exterior Walls": "External Walls",
    "Interior Walls": "Internal Walls & Partitions",
    "Window Frames": "Windows",
    "Window Glazing": "Windows",
    "Door Frames": "Doors",
    "Finishes": "Finishes",
    "Floor Finish": "Finishes",
    "Roof Insulation": "Insulation",
    "Floor Insulation": "Insulation",
    "Wall Insulation": "Insulation",
    "Miscellaneous": "Miscellaneous",
}

# Applied to all three old insulation categories.
INSULATION = {
    "Glass Wool": "Glass Wool",
    "Mineral Wool": "Mineral Wool",
    "Polystyrene": "Polystyrene (EPS/XPS)",
    "Polyurethane": "Polyurethane (PIR)",
    "Cork": "Cork",
    "Cellulose": DROP,
    "Woodwool": "Woodwool",
    "BRICKBAT COBA": "Brickbat Coba",
    "No Insulation": "No Insulation",
    "Air Gap <100mm Wide": "Air Gap",
    "Air Gap >100mm Wide": "Air Gap",
}

# old category -> { old technique name -> new technique name | DROP }.
# Techniques not listed keep their current name. Null (no-technique) joins are always kept.
OVERRIDES = {
    "Foundation": {"PCC for Footings": "Plain Cement Concrete (PCC) Footings"},
    "Basement": {
        "In-Situ Reinforced Concrete Slab": "In-Situ Reinforced Concrete",
        "Pre-cast Concrete": "Precast Concrete",
    },
    "Intermediate Floor Construction": {
        "Precast Concrete Double Tee Floor Units": "Precast Concrete Double Tee Units",
        "Thin Precast Concrete Deck and Composite In-situ Slab": "Thin Precast Concrete Deck & Composite In-Situ Slab",
    },
    "Bottom Floor Construction": {
        "Precast Concrete Double Tee Floor Units": DROP,
        "Hollow Core Precast Slab": DROP,
        "Thin Precast Concrete Deck and Composite In-situ Slab": DROP,
    },
    "Roof Construction": {
        "Steel (Zinc or Galvanized Iron) Sheets on Steel Rafters": "Metal Sheets on Steel Rafters",
        "Steel (Zinc or Galvanized iron) Sheets on Timber Rafters": "Metal Sheets on Timber Rafters",
        "Thin Precast Concrete Deck and Composite In-situ Slab": "Thin Precast Concrete Deck & Composite In-Situ Slab",
        "Micro Concrete Tiles on Timber Rafters": DROP,
        "Hollow Core Precast Slab": DROP,
        "Precast Concrete Double Tee Roof Units": DROP,
    },
    "Staircases and Ramps": {
        "In-Situ Reinforced Concrete Staircases and Ramps": "In-Situ Reinforced Concrete",
    },
    "Exterior Walls": {
        "Aluminum Profile Cladding": "Aluminium Profile Cladding",
        "Cored (with Holes) Bricks with Internal & External Plaster": "Cored Bricks with Internal & External Plaster",
    },
    "Interior Walls": {
        "In-Situ Reinforced Wall": "In-Situ Reinforced Concrete Wall",
        "Cored (with Holes) Bricks with Plaster Both Sides": "Cored Bricks with Plaster Both Sides",
        "Cement Fiber Boards on Metal Studs": "Cement Fibre Boards on Metal Studs",
        "Cement Fiber Boards on Timber Studs": DROP,
        "Precast Concrete Sandwich Panel": DROP,
        "Plasterboards on Metal Studs with Insulation": DROP,
        "Medium Weight Hollow Concrete Blocks": DROP,
        "Plasterboards on Timber Studs with Insulation": DROP,
    },
    "Window Frames": {
        "UPVC": "Frame — UPVC",
        "Aluminium  Windows": "Frame — Aluminium",
        "Aluminum": "Frame — Aluminium",
        "Timber": "Frame — Timber",
        "Wood Shutters": "Frame — Wood Shutters",
        "Steel": "Frame — Steel",
        "Ventillators": "Frame — Ventilators",
        "Aluminum Clad Timber": DROP,
        "Re-use of Existing Window Frames": DROP,
    },
    "Window Glazing": {
        "Single Glazing": "Glazing — Single",
        "Double Glazing": "Glazing — Double",
        "Triple Glazing": "Glazing — Triple",
    },
    "Door Frames": {
        "Aluminium Doors": "Aluminium",
        "Aluminum": "Aluminium",
        "Aluminum Clad Timber": "Aluminium Clad Timber",
        "Re-use of existing Door Frames": "Re-use of Existing Doors",
    },
    "Finishes": {
        "Surface layers": "Surface Layers",
        "Paint and Coatings": "Paint & Coatings",
        "Surface preparation and Treatments": "Surface Preparation & Treatments",
    },
    "Floor Finish": {
        "Stones and Tiles": "Stone & Tiles",
        "Others": "Other Floor Finishes",
        "Granites": "Granite",
        "Woods": "Timber Flooring",
    },
    "Roof Insulation": INSULATION,
    "Floor Insulation": INSULATION,
    "Wall Insulation": INSULATION,
    "Miscellaneous": {
        "Lintel, Sunshade and Sill Beam": "Lintel, Sunshade & Sill Beam",
        "Construction chemical": "Construction Chemicals",
    },
}


def forward(apps, schema_editor):
    AssemblyCategory = apps.get_model("pages", "AssemblyCategory")
    AssemblyTechnique = apps.get_model("pages", "AssemblyTechnique")
    ACT = apps.get_model("pages", "AssemblyCategoryTechnique")
    StructuralProduct = apps.get_model("pages", "StructuralProduct")

    before_classified = StructuralProduct.objects.filter(classification__isnull=False).count()
    moved = 0
    keep = set()  # destination join PKs; everything else is deleted at cleanup

    # Process every existing join and route it to its destination.
    for join in list(ACT.objects.select_related("category", "technique").all()):
        old_cat = join.category.name
        new_cat_name = CATEGORY_MAP.get(old_cat)
        if new_cat_name is None:
            # Unknown/unmapped category — leave it and its data untouched.
            continue

        old_tech = join.technique.name if join.technique else None
        if old_tech is None:
            new_tech_name = None  # keep the "Not specified" (null) join
        else:
            new_tech_name = OVERRIDES.get(old_cat, {}).get(old_tech, old_tech)  # default: keep name

        if new_tech_name == DROP:
            # This technique option is being retired. If any material still uses it,
            # don't crash and don't lose it — repoint the material(s) to the destination
            # category's "Not specified" (null-technique) join and warn, so the user can
            # re-pick a technique from the consolidated list afterwards. (Preserves the
            # material's data; only the retired technique label is cleared.)
            movers = StructuralProduct.objects.filter(classification=join)
            n = movers.count()
            if n:
                dest_cat, _ = AssemblyCategory.objects.get_or_create(
                    name=new_cat_name, defaults={"tag": NEW_CATEGORY_TAGS[new_cat_name]}
                )
                dest_null, _ = ACT.objects.get_or_create(category=dest_cat, technique=None)
                keep.add(dest_null.pk)
                movers.update(classification=dest_null)
                print(
                    f"[taxonomy] retired '{old_cat} / {old_tech}': reassigned {n} "
                    f"material(s) to '{new_cat_name} / Not specified'"
                )
            continue

        # get/create destination category (+ apply clean tag) …
        new_cat, _ = AssemblyCategory.objects.get_or_create(
            name=new_cat_name, defaults={"tag": NEW_CATEGORY_TAGS[new_cat_name]}
        )
        if new_cat.tag != NEW_CATEGORY_TAGS[new_cat_name]:
            new_cat.tag = NEW_CATEGORY_TAGS[new_cat_name]
            new_cat.save(update_fields=["tag"])

        # … technique …
        new_tech = None
        if new_tech_name is not None:
            new_tech, _ = AssemblyTechnique.objects.get_or_create(name=new_tech_name)

        # … and join.
        new_join, _ = ACT.objects.get_or_create(category=new_cat, technique=new_tech)
        keep.add(new_join.pk)

        if new_join.pk != join.pk:
            moved += StructuralProduct.objects.filter(classification=join).update(
                classification=new_join
            )

    # Ensure every new category has a "Not specified" (null-technique) join.
    for name, tag in NEW_CATEGORIES:
        cat, _ = AssemblyCategory.objects.get_or_create(name=name, defaults={"tag": tag})
        null_join, _ = ACT.objects.get_or_create(category=cat, technique=None)
        keep.add(null_join.pk)

    # Cleanup: delete every join we did NOT route a material to (this removes stale
    # old-named joins even under categories that kept their name, e.g. renamed
    # techniques in Miscellaneous/Finishes), then delete now-empty old categories.
    ACT.objects.exclude(pk__in=keep).delete()
    AssemblyCategory.objects.exclude(name__in=NEW_CATEGORY_NAMES).delete()
    # Delete technique rows no longer attached to any category.
    AssemblyTechnique.objects.filter(categories__isnull=True).delete()

    # Force the clean sort tag on every surviving target category. This covers
    # categories that pre-existed under a target name with a different tag
    # (e.g. the seed fixture's "Foundations" carried tag "extension").
    for cat_name, cat_tag in NEW_CATEGORIES:
        AssemblyCategory.objects.filter(name=cat_name).update(tag=cat_tag)

    after_classified = StructuralProduct.objects.filter(classification__isnull=False).count()
    print(
        f"\n[taxonomy] classified materials before={before_classified} "
        f"after={after_classified} (repointed {moved}); "
        f"categories now={AssemblyCategory.objects.count()}"
    )
    assert after_classified == before_classified, (
        f"Data loss! classified {before_classified} -> {after_classified}"
    )


class Migration(migrations.Migration):
    dependencies = [
        ("pages", "0045_rename_tones_unit_to_ton"),
    ]
    operations = [
        # Merges cannot be auto-reversed; restore from a DB backup if needed.
        migrations.RunPython(forward, migrations.RunPython.noop),
    ]
