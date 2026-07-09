import logging
import uuid

import openpyxl
from collections import Counter

from cities_light.models import Country

from pages.models.epd import EPD, EPDImpact, EPDType, Impact, Unit
from pages.scripts.csv_import.utils import get_superuser

logger = logging.getLogger(__name__)

FILE_PATH = "docs/TH_CFP_Final_Usable_Dataset_20260709.xlsx"
SHEET_NAME = "CFP_TGO_TH"
SOURCE = "TGO"

# Maps the sheet's "Functional_Unit" column to a Unit choice.
UNIT_MAP = {
    "kg": Unit.KG,
    "m": Unit.M,
    "m2": Unit.M2,
    "m3": Unit.M3,
    "pcs": Unit.PCS,
    "ton": Unit.TON,
}


def map_unit(raw_unit):
    if not raw_unit:
        return Unit.UNKNOWN
    return UNIT_MAP.get(str(raw_unit).strip().lower(), Unit.UNKNOWN)


def import_thailand_epds():
    """
    Import (or update) Thailand TGO CFP EPDs from the cleaned dataset.

    Matches existing EPDs by name (+ country + source), same as before, so
    re-running this command updates previously-imported rows in place.
    Old TGO EPDs from prior runs that are absent from this file are left
    untouched (not deleted) — some may still be referenced by buildings.

    Rows whose Canonical_Name_EN or Certificate_No. is not unique within the
    sheet are skipped entirely (not imported, not updated) since there's no
    reliable way to tell them apart; they're reported at the end for the
    data owner to disambiguate upstream.
    """
    superuser = get_superuser()

    try:
        country = Country.objects.get(name="Thailand")
    except Country.DoesNotExist:
        logger.error("Country 'Thailand' not found in database. Aborting.")
        return

    try:
        wb = openpyxl.load_workbook(FILE_PATH, read_only=True, data_only=True)
        ws = wb[SHEET_NAME]
    except Exception as e:
        logger.error("Failed to open Excel file: %s", e)
        return

    gwp_impact, _ = Impact.objects.get_or_create(
        impact_category="gwp",
        life_cycle_stage="a1a3",
    )

    all_rows = list(ws.iter_rows(min_row=2, values_only=True))
    wb.close()
    data_rows = [row for row in all_rows if row[0] is not None]

    # Detect duplicate identity columns up front so those rows can be skipped.
    name_counts = Counter(str(row[9]).strip() for row in data_rows if row[9])
    cert_counts = Counter(row[1] for row in data_rows if row[1])
    duplicate_names = {name for name, count in name_counts.items() if count > 1}
    duplicate_certs = {cert for cert, count in cert_counts.items() if count > 1}

    skipped_duplicate = 0
    skipped_duplicate_rows = []
    imported = 0
    updated = 0
    failure = 0
    failure_rows = []

    for row_idx, row in enumerate(data_rows, start=2):
        try:
            cert_no = row[1]           # Certificate_No.
            subcategory = row[4]       # Subcategory
            functional_unit = row[5]   # Functional_Unit
            gwp_value = row[6]         # kgCO2e
            name_en = row[9]           # Canonical_Name _EN

            name = str(name_en).strip() if name_en else ""

            if not name:
                failure += 1
                failure_rows.append(row_idx)
                continue

            if name in duplicate_names or cert_no in duplicate_certs:
                skipped_duplicate += 1
                skipped_duplicate_rows.append((row_idx, name, cert_no))
                continue

            declared_unit = map_unit(functional_unit)

            epd, created = EPD.objects.update_or_create(
                name=name,
                country=country,
                source=SOURCE,
                defaults={
                    "UUID": str(uuid.uuid4()),
                    "names": [{"lang": "en", "value": name}],
                    "type": EPDType.OFFICIAL_NON_STANDARD,
                    "declared_unit": declared_unit,
                    "declared_amount": 1.0,
                    "comment": f"Certificate: {cert_no}; Subcategory: {subcategory}" if cert_no else None,
                    "public": True,
                    "created_by_id": superuser.id,
                    "conversions": [],
                },
            )

            EPDImpact.objects.update_or_create(
                epd=epd,
                impact=gwp_impact,
                defaults={"value": float(gwp_value)},
            )

            if created:
                imported += 1
            else:
                updated += 1

        except Exception as e:
            logger.exception("Row %d: unexpected error — %s", row_idx, e)
            failure += 1
            failure_rows.append(row_idx)

    print(f"\n{'='*60}")
    print(f"Thailand TGO EPD import complete.")
    print(f"  New EPDs created:                {imported}")
    print(f"  Existing EPDs updated:           {updated}")
    print(f"  Skipped (duplicate name/cert):   {skipped_duplicate}")
    if skipped_duplicate_rows:
        print(f"    Rows skipped (row, name, certificate):")
        for row_idx, name, cert_no in skipped_duplicate_rows:
            print(f"      row {row_idx}: {name!r} / {cert_no!r}")
    print(f"  Failed rows (errors):            {failure}  {failure_rows if failure_rows else ''}")
    print(f"{'='*60}\n")
