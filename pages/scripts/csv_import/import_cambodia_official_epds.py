"""Load the six official Cambodian cement EPDs.

Cambodia had a single official (manufacturer) EPD in BEAT against 178 derived
generics, even though six verified declarations exist. This loads the other
five and keeps the existing one, renaming it so the two Chip Mong INSEE
products are distinguishable.

Source documents: EPD International (environdec.com), EN 15804+A2, ISO 14025,
cradle-to-gate A1-A3, all declared per 1 metric tonne (1,000 kg). Values were
read from the PDFs in the project EPD library, not retyped from a summary.

    EPD-IES-0022825  K Plastering Cement, bagged      420 kgCO2e/t
    EPD-IES-0022826  5-Star Cement, bagged            582
    EPD-IES-0022824  K Cement, bagged                 638
    EPD-IES-0016315  Camel Power Flow (Chip Mong)     661
    EPD-IES-0022828  K Cement, bulk                   741
    EPD-IES-0022827  SCG Cement, bagged               749
    (already present)  Camel Opti-Flow (Chip Mong)    844.8

Manufacturers: KCC Kampot Cement Co., Ltd (Kampot Province) and Chip Mong INSEE
Cement Corporation. Both plants are in Cambodia; SCG and Siam City Cement
appear in the documents as parent companies, not as the production site.

Idempotent: keyed on (name, country), so re-running updates rather than
duplicates.
"""

import logging
from decimal import Decimal

import pandas as pd

from pages.models.epd import EPD, EPDType, Impact, EPDImpact
from pages.scripts.csv_import.utils import get_country, get_superuser

logger = logging.getLogger(__name__)

FILE_PATH = "pages/data/cambodia_official_epds.csv"
COUNTRY = "Cambodia"
SOURCE_LABEL = "EPD International (environdec.com)"

# The existing record is Camel Opti-Flow (Bulk): its 844.8 kgCO2e/t matches
# "Global Warming Potential, total 844.8" in that EPD exactly. Renaming makes it
# distinguishable from Camel Power Flow, which this script adds. Materials
# reference the EPD by id, so the rename is display-only and safe.
RENAME_EXISTING = {
    "Chip Mong INSEE Cement": "Camel Opti-Flow Cement (Chip Mong INSEE)",
}


def _set_gwp(epd, stage, value):
    """Attach or update one GWP impact on the EPD."""
    if value is None or pd.isna(value):
        return
    impact, _ = Impact.objects.get_or_create(
        impact_category="gwp", life_cycle_stage=stage
    )
    EPDImpact.objects.update_or_create(
        epd=epd, impact=impact, defaults={"value": Decimal(str(value))}
    )


def import_cambodia_official_epds():
    superuser = get_superuser()
    country = get_country(COUNTRY)

    # --- rename the existing record so the two Chip Mong products are distinct
    for old, new in RENAME_EXISTING.items():
        updated = EPD.objects.filter(name=old, country=country).update(name=new)
        if updated:
            logger.info("renamed %r -> %r (%d record)", old, new, updated)

    try:
        df = pd.read_csv(FILE_PATH)
    except FileNotFoundError:
        logger.error("%s not found", FILE_PATH)
        return

    created = updated = 0
    for _, row in df.iterrows():
        epd, was_created = EPD.objects.update_or_create(
            name=row["name"],
            country=country,
            defaults={
                "type": EPDType.OFFICIAL,
                "declared_unit": row["declared_unit"],
                "declared_amount": Decimal(str(row["declared_amount"])),
                "source": row["source"],
                "created_by": superuser,
                "public": True,
                # Cement. Matches the category already used by the existing
                # Cambodian cement EPD.
                "category_id": "3",
                # `names` is NOT NULL and `UUID` has no default. The existing
                # Cambodian record uses the EPD registration number pattern for
                # one and a single English name entry for the other.
                "UUID": row["epd_registration"],
                "names": [{"lang": "en", "value": row["name"]}],
                "conversions": [],
            },
        )
        _set_gwp(epd, "a1a3", row.get("gwp_a1a3"))

        if was_created:
            created += 1
        else:
            updated += 1
        logger.info(
            "%s  %s  %.1f kgCO2e per %s kg  [%s]",
            "created" if was_created else "updated",
            row["name"], row["gwp_a1a3"], row["declared_amount"],
            row["epd_registration"],
        )

    logger.info(
        "Cambodia official EPDs: %d created, %d updated (now %d official in total)",
        created, updated,
        EPD.objects.filter(country=country, type=EPDType.OFFICIAL).count(),
    )
