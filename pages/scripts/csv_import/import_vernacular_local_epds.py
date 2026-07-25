"""Load vernacular / local low-carbon material EPDs (literature-sourced generics).

These promote traditional / local-architecture materials (structural bamboo,
laterite, cement-stabilised rammed earth, lime-jaggery mortar) across the ALCBT
countries. Values are cradle-to-gate A1-A3 **fossil/process** GWP (biogenic carbon
excluded for now; a separate biogenic indicator is a planned phase 2), taken from
peer-reviewed LCA literature and clearly labelled as regional proxies — not
manufacturer EPDs. Loaded as type=GENERIC with a distinct source so they appear as
fallbacks for all countries and stay traceable/removable.

Per-material citations + data-quality notes live in the methodology handbook
(Local_Vernacular_Materials_EmbodiedCarbon_Research.md). CSV:
pages/data/generic_epds_vernacular_local.csv. Idempotent (name, country, source).
"""

import logging

import pandas as pd

from pages.models.epd import EPD, EPDType
from pages.scripts.csv_import.utils import (
    add_impacts,
    get_conversions,
    get_country,
    get_superuser,
)
from pages.scripts.csv_import.import_generic_structural_epds import (
    get_declared_amount,
    impact_columns,
    _norm_unit,
)
from pages.scripts.csv_import.import_ifc_localized_epds import _resolve_category

logger = logging.getLogger(__name__)

SOURCE = "Vernacular/local (literature)"
FILE_PATH = "pages/data/generic_epds_vernacular_local.csv"


def import_vernacular_local_epds():
    superuser = get_superuser()
    try:
        df = pd.read_csv(FILE_PATH, sep=";")
    except Exception as e:
        print(f"Error reading CSV file: {e}")
        return

    created = updated = failure = 0
    failure_list = []
    for index, row in df.iterrows():
        try:
            name = str(row["name"]).strip()
            defaults = {
                "names": [{"lang": "en", "value": name}],
                "public": True,
                "conversions": get_conversions(row),
                "category": _resolve_category(row),
                "declared_unit": _norm_unit(row["declared_unit"]),
                "type": EPDType.GENERIC,
                "declared_amount": get_declared_amount(row),
                "comment": (
                    "Vernacular/local material proxy from peer-reviewed LCA literature "
                    "(cradle-to-gate A1-A3, fossil/process; biogenic carbon excluded). "
                    "Regional proxy, not a manufacturer EPD - see BEAT methodology "
                    "handbook for the per-material source."
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
            created += was_created
            updated += (not was_created)
        except Exception as e:
            logger.exception("Error in row %s", index)
            failure += 1
            failure_list.append(index)
            raise Exception(f"Error in row {index}: {e}\n  Row: {row}")

    print(
        f"\033[32mVernacular/local EPDs: {created} created, {updated} updated, "
        f"{failure} failed. Rows: {failure_list}\033[0m"
    )
