import re
import uuid
import logging
import openpyxl

from cities_light.models import Country

from pages.models.epd import EPD, EPDImpact, EPDType, Impact, Unit
from pages.scripts.csv_import.utils import get_superuser

logger = logging.getLogger(__name__)

FILE_PATH = "docs/TH_CFP-TGO_Data_final(18Feb2026).xlsx"
SOURCE = "TGO"

UNIT_MAP = {
    "m2": Unit.M2,
    "m3": Unit.M3,
    "kg": Unit.KG,
    "m": Unit.M,
    "pcs": Unit.PCS,
    "ton": Unit.TONES,
    "hour": Unit.UNKNOWN,
    "gallon": Unit.UNKNOWN,
}


def parse_cf_volume(raw):
    """
    Parse strings like '268 gCO2e', '22.5 kgCO2e', or '14.6 kg'.
    Returns (value_in_kg, True) or (None, False) if unparseable/null.
    gCO2e values are divided by 1000 to convert to kgCO2e.
    Bare 'kg' values are treated as kgCO2e.
    """
    if not raw:
        return None, False
    raw = str(raw).strip()
    match = re.match(r"^([\d.]+)\s*(g|kg)(?:CO2e)?$", raw, re.IGNORECASE)
    if not match:
        return None, False
    value = float(match.group(1))
    if match.group(2).lower() == "g":
        value = value / 1000
    return value, True


def map_unit(raw_unit):
    if not raw_unit or str(raw_unit).strip() in ("0", "None", ""):
        return Unit.UNKNOWN
    return UNIT_MAP.get(str(raw_unit).strip().lower(), Unit.UNKNOWN)


def import_thailand_epds():
    superuser = get_superuser()

    try:
        country = Country.objects.get(name="Thailand")
    except Country.DoesNotExist:
        logger.error("Country 'Thailand' not found in database. Aborting.")
        return

    try:
        wb = openpyxl.load_workbook(FILE_PATH, read_only=True, data_only=True)
        ws = wb["Data"]
    except Exception as e:
        logger.error("Failed to open Excel file: %s", e)
        return

    gwp_impact, _ = Impact.objects.get_or_create(
        impact_category="gwp",
        life_cycle_stage="a1a3",
    )

    skipped_excluded = 0    # unit status != Good
    skipped_no_unit = 0     # blank declared unit
    skipped_no_name = 0     # blank English name
    imported_with_gwp = 0   # EPD + GWP impact created
    imported_no_gwp = 0     # EPD created, CF Volume null so no impact
    failure = 0
    failure_rows = []

    for row_idx, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
        if all(v is None for v in row):
            break
        if len(row) < 26:
            continue

        try:
            unit_status = row[1]           # col B
            declared_unit_raw = row[2]     # col C
            declared_amount_raw = row[3]   # col D
            name = row[21]                 # col V - English name
            cf_volume_raw = row[25]        # col Z

            if str(unit_status).strip().lower() != "good":
                skipped_excluded += 1
                continue

            if not name or str(name).strip() == "":
                skipped_no_name += 1
                continue

            if not declared_unit_raw or str(declared_unit_raw).strip() in ("", "0", "None"):
                skipped_no_unit += 1
                continue

            name = str(name).strip()
            declared_unit = map_unit(declared_unit_raw)

            try:
                declared_amount = float(declared_amount_raw) if declared_amount_raw not in (None, "", "0", 0) else 1.0
                if declared_amount <= 0:
                    declared_amount = 1.0
            except (ValueError, TypeError):
                declared_amount = 1.0

            epd, _ = EPD.objects.update_or_create(
                name=name,
                country=country,
                source=SOURCE,
                defaults={
                    "UUID": str(uuid.uuid4()),
                    "names": [{"lang": "en", "value": name}],
                    "type": EPDType.OFFICIAL_NON_STANDARD,
                    "declared_unit": declared_unit,
                    "declared_amount": declared_amount,
                    "public": True,
                    "created_by_id": superuser.id,
                    "conversions": [],
                },
            )

            gwp_value, parseable = parse_cf_volume(cf_volume_raw)
            if parseable:
                EPDImpact.objects.update_or_create(
                    epd=epd,
                    impact=gwp_impact,
                    defaults={"value": gwp_value},
                )
                imported_with_gwp += 1
            else:
                imported_no_gwp += 1
                logger.info(
                    "Row %d: '%s' imported without GWP impact — CF Volume null/unparseable: %r",
                    row_idx, name, cf_volume_raw,
                )

        except Exception as e:
            logger.exception("Row %d: unexpected error — %s", row_idx, e)
            failure += 1
            failure_rows.append(row_idx)

    wb.close()

    total_imported = imported_with_gwp + imported_no_gwp
    print(f"\n{'='*60}")
    print(f"Thailand TGO EPD import complete.")
    print(f"  Skipped (Unit status != Good):  {skipped_excluded}")
    print(f"  Skipped (blank declared unit):  {skipped_no_unit}")
    print(f"  Skipped (missing name):         {skipped_no_name}")
    print(f"  Total EPDs imported:            {total_imported}")
    print(f"    - with GWP impact:            {imported_with_gwp}")
    print(f"    - without GWP impact:         {imported_no_gwp}  (CF Volume null — EPDImpact.value does not allow null)")
    print(f"  Failed rows (errors):           {failure}  {failure_rows if failure_rows else ''}")
    print(f"{'='*60}\n")
