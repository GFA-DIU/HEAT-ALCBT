import logging
import re
import uuid
from collections import Counter

import openpyxl

from cities_light.models import Country

from pages.models.assembly import StructuralProduct
from pages.models.building import OperationalProduct, SimulatedOperationalProduct
from pages.models.epd import EPD, EPDImpact, EPDType, Impact, MaterialCategory, Unit
from pages.scripts.csv_import.utils import get_superuser

logger = logging.getLogger(__name__)

FILE_PATH = "docs/TH_CFP_Final_Usable_Dataset_20260709.xlsx"
SHEET_NAME = "CFP_TGO_TH"
SOURCE = "TGO"

# Suffix appended to a COPY created when a building-referenced ("used") EPD has a
# different value in the new file — so the original (still referenced by buildings)
# is preserved untouched and the updated data is available as a distinct record.
UPDATE_MARKER = " (TGO 2026 update)"

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


# Rebar detection (scoped to the steel subcategory only, so it never catches
# "reinforced concrete/AAC" products). Matches TGO rebar/mesh product names.
REBAR_NAME_RE = re.compile(
    r"(deformed bar|round bar|reinforcing bar|\brebar\b|reinforcement mesh|deformed .*wire mesh)",
    re.IGNORECASE,
)

# TGO Subcategory -> top-level MaterialCategory (name_en). Sets EPD.category so the
# EPD-library category chip isn't empty and the material dashboard can group TGO EPDs.
# Steel is handled separately (name-based rebar vs steel split) in resolve_category().
TGO_SUBCATEGORY_TO_CATEGORY = {
    "Insulation": "Insulation materials",
    "Concrete": "Mineral building products",
    "Cement": "Mineral building products",
    "Mortar": "Mineral building products",
    "Masonry": "Mineral building products",
    "Paint and Coating": "Coverings",
    "Flooring": "Coverings",
    "Ceiling": "Coverings",
    "Roofing": "Coverings",
    "Wall Finishing / Panel": "Coverings",
    "Pipe": "Building service engineering",
    "Pipe-accessory": "Building service engineering",
    "Door / Window / Opening": "Components for windows and curtain walls",
    "Chemical / Bonding / Adhesive": "Others",
}


def _used_tgo_epd_ids():
    """EPD ids (source=TGO) referenced by any building material — must never be
    deleted or modified (deleting cascades to those building materials)."""
    ids = set()
    for Model in (StructuralProduct, OperationalProduct, SimulatedOperationalProduct):
        ids.update(
            Model.objects.filter(epd__source=SOURCE).values_list("epd_id", flat=True)
        )
    return ids


def import_thailand_epds():
    """Selective replace of Thailand TGO CFP EPDs from the cleaned dataset.

    Strategy (per data owner):
      - New file is authoritative for all EPDs NOT referenced by a building.
      - EPDs referenced by a building ("used") are NEVER modified or deleted:
          * if the new file's value (GWP + unit) matches → left as-is;
          * if it differs → a COPY is created (name + UPDATE_MARKER) carrying the
            new value, so buildings keep their original and the update is available.
      - Old TGO EPDs that are unused and absent from the new file are DELETED.

    Idempotent: re-running updates in place and re-deletes stale rows.
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
        impact_category="gwp", life_cycle_stage="a1a3"
    )

    # Resolve TGO subcategory (+ product name for steel) -> MaterialCategory row.
    _cat_cache = {}

    def get_category(name):
        if name and name not in _cat_cache:
            _cat_cache[name] = (
                MaterialCategory.objects.filter(name_en=name).order_by("level").first()
            )
        return _cat_cache.get(name)

    def resolve_category(subcat, name=""):
        sc = str(subcat).strip() if subcat else ""
        # Steel: split rebar (-> "Steel reinforing bar" -> dashboard "Rebar") from
        # all other steel (-> "Steel" -> dashboard "Steel"), by product name.
        if sc in ("Steel / Metal", "Wire / Welding Rod"):
            if REBAR_NAME_RE.search(name or ""):
                return get_category("Steel reinforing bar")
            return get_category("Steel")
        return get_category(TGO_SUBCATEGORY_TO_CATEGORY.get(sc))

    all_rows = list(ws.iter_rows(min_row=2, values_only=True))
    wb.close()
    data_rows = [row for row in all_rows if row[0] is not None]

    # Skip rows whose identity columns aren't unique within the sheet.
    name_counts = Counter(str(row[9]).strip() for row in data_rows if row[9])
    cert_counts = Counter(row[1] for row in data_rows if row[1])
    duplicate_names = {n for n, c in name_counts.items() if c > 1}
    duplicate_certs = {c for c, n in cert_counts.items() if n > 1}

    used_ids = _used_tgo_epd_ids()
    keep_ids = set(used_ids)  # ids we must not delete at cleanup

    created = updated = matched = copied = skipped = failure = 0
    skipped_rows = []
    failure_rows = []

    def _write_epd(name, unit, gwp_value, cert, subcat):
        """Create/update an EPD (+ its GWP A1-A3 impact) and return it."""
        epd, was_created = EPD.objects.update_or_create(
            name=name,
            country=country,
            source=SOURCE,
            defaults={
                "names": [{"lang": "en", "value": name}],
                "type": EPDType.OFFICIAL_NON_STANDARD,
                "declared_unit": unit,
                "declared_amount": 1.0,
                "category": resolve_category(subcat, name),
                "comment": f"Certificate: {cert}; Subcategory: {subcat}" if cert else None,
                "public": True,
                "created_by_id": superuser.id,
                "conversions": [],
            },
            create_defaults={
                "names": [{"lang": "en", "value": name}],
                "type": EPDType.OFFICIAL_NON_STANDARD,
                "declared_unit": unit,
                "declared_amount": 1.0,
                "category": resolve_category(subcat, name),
                "comment": f"Certificate: {cert}; Subcategory: {subcat}" if cert else None,
                "public": True,
                "created_by_id": superuser.id,
                "conversions": [],
                "UUID": str(uuid.uuid4()),
            },
        )
        EPDImpact.objects.update_or_create(
            epd=epd, impact=gwp_impact, defaults={"value": float(gwp_value)}
        )
        return epd, was_created

    for row_idx, row in enumerate(data_rows, start=2):
        try:
            cert_no = row[1]
            subcategory = row[4]
            functional_unit = row[5]
            gwp_value = row[6]
            name_en = row[9]

            name = str(name_en).strip() if name_en else ""
            if not name:
                failure += 1
                failure_rows.append(row_idx)
                continue

            if name in duplicate_names or cert_no in duplicate_certs:
                skipped += 1
                skipped_rows.append((row_idx, name, cert_no))
                continue

            unit = map_unit(functional_unit)
            existing = EPD.objects.filter(
                name=name, country=country, source=SOURCE
            ).first()

            if existing is None:
                epd, _ = _write_epd(name, unit, gwp_value, cert_no, subcategory)
                keep_ids.add(epd.id)
                created += 1

            elif existing.id in used_ids:
                # Used by a building — never modify. Keep it, and copy if changed.
                keep_ids.add(existing.id)
                cur = EPDImpact.objects.filter(epd=existing, impact=gwp_impact).first()
                cur_gwp = cur.value if cur else None
                same = (
                    existing.declared_unit == unit
                    and cur_gwp is not None
                    and abs(cur_gwp - float(gwp_value)) < 1e-9
                )
                if same:
                    matched += 1
                else:
                    copy, _ = _write_epd(
                        name + UPDATE_MARKER, unit, gwp_value, cert_no, subcategory
                    )
                    keep_ids.add(copy.id)
                    copied += 1

            else:
                # Unused existing — update in place to the new value.
                _write_epd(name, unit, gwp_value, cert_no, subcategory)
                keep_ids.add(existing.id)
                updated += 1

        except Exception as e:
            logger.exception("Row %d: unexpected error — %s", row_idx, e)
            failure += 1
            failure_rows.append(row_idx)

    # (Re)set category on ALL TGO EPDs from the subcategory stored in their comment
    # + product name — covers in-use rows we don't rewrite and corrects any earlier
    # coarse mapping. Category is display / dashboard only — it does NOT affect any
    # building's carbon calculation, so it is safe to update on in-use rows.
    backfilled = 0
    for e in EPD.objects.filter(source=SOURCE):
        # Rebar is identifiable by product name even when the subcategory metadata
        # is missing (legacy in-use rows). Otherwise use the subcategory in comment.
        if REBAR_NAME_RE.search(e.name or ""):
            cat = get_category("Steel reinforing bar")
        else:
            m = re.search(r"Subcategory:\s*(.+?)\s*$", e.comment or "")
            cat = resolve_category(m.group(1), e.name) if m else None
        if cat and e.category_id != cat.id:
            e.category = cat
            e.save(update_fields=["category"])
            backfilled += 1

    # Delete stale TGO EPDs: unused AND not part of the new file / copies.
    stale = EPD.objects.filter(source=SOURCE).exclude(id__in=keep_ids)
    deleted = stale.count()
    stale.delete()

    print(f"\n{'='*60}")
    print("Thailand TGO EPD selective import complete.")
    print(f"  New EPDs created:                {created}")
    print(f"  Unused EPDs updated in place:    {updated}")
    print(f"  Used EPDs unchanged (matched):   {matched}")
    print(f"  Used EPDs changed -> copy made:   {copied}")
    print(f"  Stale unused EPDs deleted:       {deleted}")
    print(f"  Categories backfilled:           {backfilled}")
    print(f"  Skipped (duplicate name/cert):   {skipped}")
    print(f"  Failed rows:                     {failure}  {failure_rows if failure_rows else ''}")
    print(f"{'='*60}\n")
