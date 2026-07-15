import logging
import pandas as pd

from pages.models.epd import EPD, EPDType, MaterialCategory
from pages.scripts.csv_import.utils import (
    add_impacts,
    get_conversions,
    get_country,
    get_superuser,
)
from pages.scripts.epd_categorization import resolve_by_name, category_by_name

logger = logging.getLogger(__name__)

SOURCE = "GFA-HEAT"

impact_columns = [
    "penrt_a1a3 [MJ]",
    "penrt_c3 [MJ]",
    "penrt_c4 [MJ]",
    "penrt_d [MJ]",
    "gwp_a1a3 [kgCo2e]",
    "gwp_c3 [kgCo2e]",
    "gwp_c4 [kgCo2e]",
    "gwp_d [kgCo2e]",
]

# Normalise unicode / short unit spellings from the source file to the Unit codes
# used in the DB (e.g. "m³" -> "m3", "t" -> "ton"). Anything not listed is passed
# through unchanged (already a valid code).
_UNIT_NORMALIZE = {"m³": "m3", "m²": "m2", "m¹": "m", "t": "ton", "M3": "m3", "M2": "m2"}


def _norm_unit(u):
    return _UNIT_NORMALIZE.get(str(u).strip(), str(u).strip())


def get_category(row):
    """Resolve the Ökobaudat category from the level indices when it exists, else
    fall back to the shared name-based resolver. Never creates placeholder rows."""
    if not pd.isna(row["level_2_index"]):
        if len(str(row["level_2_index"])) == 1:
            level_2_index = f"0{row['level_2_index']}"
        else:
            level_2_index = str(row["level_2_index"])
        category_id = f"{row['level_0_index']}.{row['level_1_index']}.{level_2_index}"
        cat = MaterialCategory.objects.filter(category_id=category_id, level=3).first()
        if cat:
            return cat
    return resolve_by_name(row.get("name")) or category_by_name("Unknown")


def get_declared_amount(row):
    declared_amount = row.get("declared_amount", 1.0)
    if pd.isna(declared_amount):
        declared_amount = 1.0
    return declared_amount


def import_generic_structural_epds():
    """Refresh generic (GFA-HEAT) structural EPDs from pages/data/generic_EPDs.csv.

    Idempotent update-in-place, keyed on (name, country, source): existing EPDs are
    updated (values, unit, conversions, category, impacts) and missing ones created.
    Re-running never duplicates. Generic EPDs are placeholders for countries lacking
    a real EPD, so refreshed values apply everywhere they are used (per data owner).
    """
    file_path = "pages/data/generic_EPDs.csv"
    superuser = get_superuser()

    try:
        df = pd.read_csv(file_path, sep=";")
    except Exception as e:
        print(f"Error reading CSV file: {e}")
        return

    created = updated = failure = 0
    failure_list = []
    for index, row in df.iterrows():
        try:
            # Strip the name: some source rows carry stray leading whitespace
            # (tabs/newlines). Without stripping, update_or_create fails to match
            # the existing clean-named EPD and inserts a duplicate.
            name = str(row["name"]).strip()
            defaults = {
                "names": [{"lang": "en", "value": name}],
                "public": True,
                "conversions": get_conversions(row),
                "category": get_category(row),
                "declared_unit": _norm_unit(row["declared_unit"]),
                "type": EPDType.GENERIC,
                "declared_amount": get_declared_amount(row),
                "comment": (
                    f"Created based on {row['UUID']} "
                    f"(https://oekobaudat.de/OEKOBAU.DAT/datasetdetail/process.xhtml?uuid={row['UUID']})"
                ),
                "created_by_id": superuser.id,
            }
            epd, was_created = EPD.objects.update_or_create(
                name=name,
                country=get_country(row["country"]),
                source=SOURCE,
                defaults=defaults,
            )
            add_impacts(row, epd, impact_columns)
            if was_created:
                created += 1
            else:
                updated += 1
        except Exception as e:
            logger.exception("Error in row %s", index)
            failure += 1
            failure_list.append(index)
            raise Exception(f"Error in row {index}: {e}\n  Row: {row}")

    print(
        f"\033[32mGeneric structural EPDs: {created} created, {updated} updated, "
        f"{failure} failed. Rows: {failure_list}\033[0m"
    )
