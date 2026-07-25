"""Load grid-localized IFC-India generic EPDs for the non-India ALCBT countries.

Background
----------
BEAT's shared generic set (74 materials x 5 countries) lacks several basic
materials (raw aggregate/sand, cement binders OPC/PPC/slag/GGBS/fly-ash,
aluminium, glass, copper, floor tiles ...). India additionally has the IFC
"India Construction Materials Database" (thinkstep/GaBi, 2017) via EDGE. Those
India values are re-localized to Indonesia/Vietnam/Cambodia/Thailand by rescaling
ONLY the electricity-attributable GWP (from the report's Table 16 breakdown) by
each country's grid emission factor:

    GWP_country = (Total - Elec_GWP) + Elec_GWP * (EF_country / EF_India_2012)

with EF_India_2012 ~= 0.95 kg CO2e/kWh (GaBi India 2012 anchor) and BEAT grids
ID 0.78 / VN 0.659 / KH 0.588 / TH 0.475. Process/kiln-dominated materials
(cement, brick) barely move; electricity-heavy ones (aluminium, glass) shift.
See docs / memory `epd-generic-localization-ifc` for the full derivation.

The CSV `pages/data/generic_epds_ifc_localized.csv` carries the per-country
localized GWP A1-A3 (kg CO2e per kg). Rows are loaded as type=GENERIC with a
distinct source so they are traceable and separable from the Okobaudat-based
GFA-HEAT generics. Idempotent: keyed on (name, country, source).
"""

import logging

import pandas as pd

from pages.models.epd import EPD, EPDType, MaterialCategory
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
from pages.scripts.epd_categorization import resolve_by_name, category_by_name

logger = logging.getLogger(__name__)

SOURCE = "IFC-India (grid-localized)"
FILE_PATH = "pages/data/generic_epds_ifc_localized.csv"


def _resolve_category(row):
    """Float-safe category resolver.

    This CSV is mostly blank in the level_*_index columns, so pandas types them as
    float (1 -> 1.0). Build the Okobaudat id from int-cast values when present,
    else fall back to the shared name resolver.
    """
    idx = row.get("level_2_index")
    if idx is not None and not pd.isna(idx):
        l0 = int(float(row["level_0_index"]))
        l1 = int(float(row["level_1_index"]))
        l2 = int(float(idx))
        category_id = f"{l0}.{l1}.{l2:02d}"
        cat = MaterialCategory.objects.filter(category_id=category_id, level=3).first()
        if cat:
            return cat
    return resolve_by_name(str(row.get("name"))) or category_by_name("Unknown")


def import_ifc_localized_epds():
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
            country = get_country(row["country"])
            defaults = {
                "names": [{"lang": "en", "value": name}],
                "public": True,
                "conversions": get_conversions(row),
                "category": _resolve_category(row),
                "declared_unit": _norm_unit(row["declared_unit"]),
                "type": EPDType.GENERIC,
                "declared_amount": get_declared_amount(row),
                "comment": (
                    "Generic regional proxy from IFC India Construction Materials "
                    "Database (GaBi 2017, via EDGE); GWP A1-A3 grid-localized to this "
                    "country (electricity share rescaled to national grid EF; India "
                    "2012 anchor ~0.95). Proxy, not a manufacturer EPD."
                ),
                "created_by_id": superuser.id,
            }
            epd, was_created = EPD.objects.update_or_create(
                name=name,
                country=country,
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
        f"\033[32mIFC-localized generic EPDs: {created} created, {updated} updated, "
        f"{failure} failed. Rows: {failure_list}\033[0m"
    )
