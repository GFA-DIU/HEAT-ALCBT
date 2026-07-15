"""
Add the "Building Part" family grouping to AssemblyCategory and assign each of the
14 consolidated categories to its family (Substructure / Superstructure /
Envelope & Openings / Finishes & Other). See docs/taxonomy_mapping.md.
"""
from django.db import migrations, models

FAMILY_OF = {
    # substructure
    "Foundations": "substructure",
    "Basement & Retaining Walls": "substructure",
    # superstructure
    "Columns": "superstructure",
    "Beams & Slabs": "superstructure",
    "Ground Floor": "superstructure",
    "Roof": "superstructure",
    "Staircases & Ramps": "superstructure",
    # envelope & openings
    "External Walls": "envelope",
    "Internal Walls & Partitions": "envelope",
    "Windows": "envelope",
    "Doors": "envelope",
    # finishes & other
    "Finishes": "finishes",
    "Insulation": "finishes",
    "Miscellaneous": "finishes",
}


def assign_families(apps, schema_editor):
    AssemblyCategory = apps.get_model("pages", "AssemblyCategory")
    for name, family in FAMILY_OF.items():
        AssemblyCategory.objects.filter(name=name).update(family=family)
    # Warn (don't fail) if any category ended up without a family.
    missing = list(
        AssemblyCategory.objects.filter(family="").values_list("name", flat=True)
    )
    if missing:
        print(f"\n[taxonomy] WARNING: categories without a family: {missing}")


class Migration(migrations.Migration):
    dependencies = [
        ("pages", "0046_consolidate_assembly_taxonomy"),
    ]
    operations = [
        migrations.AddField(
            model_name="assemblycategory",
            name="family",
            field=models.CharField(
                blank=True,
                choices=[
                    ("substructure", "Substructure"),
                    ("superstructure", "Superstructure"),
                    ("envelope", "Envelope & Openings"),
                    ("finishes", "Finishes & Other"),
                ],
                max_length=20,
                verbose_name="Building Part",
            ),
        ),
        migrations.RunPython(assign_families, migrations.RunPython.noop),
    ]
