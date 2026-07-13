from django.db import migrations

# Old (pre-cleanup) energy-carrier names -> new uniform Title Case, TGO-aligned.
# Keyed on the normalised (stripped + lowercased) old name so it also catches
# whitespace-padded variants (e.g. a trailing-space "electricity ").
#
# WHY A MIGRATION: the operational loader (import_generic_operational_epds) matches
# existing EPDs by exact name. The refreshed CSV uses the new names, so without this
# rename a production run would fail to match the old-named rows and INSERT duplicates.
# Renaming here (by PK, references preserved) lets the loader update in place instead.
OLD_TO_NEW = {
    "cerosin": "Kerosene",
    "char coal": "Charcoal",
    "coal": "Coal",
    "diesel": "Diesel",
    "electricity": "Electricity",
    "fire wood (log wood)": "Firewood (Log Wood)",
    "fire wood (wood chips)": "Firewood (Wood Chips)",
    "fire wood (wood pellets)": "Firewood (Wood Pellets)",
    "heavy fuel oil": "Heavy Fuel Oil",
    "light fuel oil": "Light Fuel Oil",
    "lignite": "Lignite",
    "liquefied petroleum gas (lpg)": "Liquefied Petroleum Gas (LPG)",
    "natural gas": "Natural Gas",
}
NEW_TO_OLD = {v: k for k, v in OLD_TO_NEW.items()}


def _rename(apps, mapping, key_fn):
    EPD = apps.get_model("pages", "epd")
    qs = EPD.objects.filter(source="GFA-HEAT", declared_unit="kwh")
    for epd in qs:
        new = mapping.get(key_fn(epd.name))
        if not new or epd.name == new:
            continue
        # Never create a duplicate: skip if another carrier in the same country
        # already holds the target name.
        clash = (
            EPD.objects.filter(
                source="GFA-HEAT",
                declared_unit="kwh",
                country_id=epd.country_id,
                name=new,
            )
            .exclude(pk=epd.pk)
            .exists()
        )
        if clash:
            continue
        epd.name = new
        epd.names = [{"lang": "en", "value": new}]
        epd.save(update_fields=["name", "names"])


def forwards(apps, schema_editor):
    _rename(apps, OLD_TO_NEW, lambda n: (n or "").strip().lower())


def backwards(apps, schema_editor):
    _rename(apps, NEW_TO_OLD, lambda n: (n or "").strip())


class Migration(migrations.Migration):

    dependencies = [
        ("pages", "0048_alter_assembly_dimension"),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
