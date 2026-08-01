"""Backfill missing EPD conversion factors so kg-declared materials can be
converted to kg in the carbon calculation.

Background
----------
Several kg-declared EPDs used on imported buildings carry no (or insufficient)
conversion factors, so the calc cannot turn an area/volume/length/pcs assembly
quantity into kg and raises "Cannot convert ... to kg". This command adds the
missing conversion(s) to the specific EPDs involved.

Corruption-aware choice of conversion TYPE
------------------------------------------
On these imported buildings the per-product thickness/cross-section/piece-count
field was corrupted (set equal to the assembly's area/length value). The calc
only touches that corrupted field on *some* conversion paths:

  * AREA + kg   : "area density"  -> kg = area   x density        (IGNORES thickness)   ✅
                  "volume density"-> kg = area   x THICKNESS x rho (USES corrupt cm)    ❌
  * LENGTH + kg : "linear density"-> kg = length x density        (IGNORES cross-sec)   ✅
                  "volume density"-> kg = length x CROSS-SEC x rho (USES corrupt cm²)   ❌
  * VOLUME + kg : "volume density"-> kg = volume x density        (clean, uses volume)  ✅
  * PCS + kg    : "conversion factor to 1 kg" (= pieces per kg); kg = pcs / factor.
                  The "pieces" value is really a mass here, so factor = 1.0 -> kg = value.

So we deliberately add AREA/LINEAR/VOLUME densities (never volume density for an
area/length material) to bypass the corrupted fields and produce sensible mass.

Values
------
Group A (material constants, defensible):
  OPC cement volume density 1440, Waterproofing admixture 1050, Granite area
  density 54 (= 2700 kg/m³ x 20 mm).
Group B (best-effort estimates, flagged in the EPD comment — no single correct
value; depend on the actual product/application):
  paints, anti-termite, steel door frame, u-PVC frame, reinforcement wire.

Safety
------
  * ADDITIVE ONLY — a conversion is added only if one with that name is absent;
    existing conversions are never modified or removed. Idempotent (re-runs add
    nothing). Transactional. --dry-run writes nothing.
  * Targets specific EPD ids (the instances causing the errors); other EPDs are
    untouched.

Usage:
    python manage.py backfill_epd_conversions --dry-run
    python manage.py backfill_epd_conversions
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from pages.models.epd import EPD

_UNIT = {
    "volume density": "kg/m^3",
    "area density": "kg/m^2",
    "linear density": "kg/m",
    "conversion factor to 1 kg": "-",
}
_UNIT_DESC = {
    "volume density": "kilograms per cubic metre",
    "area density": "kilograms per square metre",
    "linear density": "kilograms per metre",
    "conversion factor to 1 kg": "Without unit",
}

# (epd_id, human name, [(conversion name, value, is_estimate)])
_PLAN = [
    ("24251eb0-55b8-47c6-a073-bd1df665bf41", "Aditya Birla OPC (cement)",
        [("volume density", "1440", False)]),
    ("b96c72bc-e589-404e-a051-0e70fdb743b7", "Waterproofing admixture",
        [("volume density", "1050", False)]),
    ("2df75961-bffe-4545-bcf1-39a3e65f3481", "Granite",
        [("area density", "54", False)]),  # 2700 kg/m3 x 20 mm slab
    ("1fb75064-468b-40b3-8c58-8fed3b0fd85f", "Acrylic emulsion paint",
        [("area density", "0.3", True)]),
    ("04830f10-a0f3-4948-9f4f-1a1a39460420", "Acrylic basecoat paint",
        [("area density", "0.4", True)]),
    ("08df9a25-ea8a-4c04-8f82-e5e20c13fff9", "Anti termite treatment",
        [("area density", "0.5", True)]),
    ("175c7a96-2b68-4f11-97f2-1163dc8af31a", "Steel door frame",
        [("area density", "9", True), ("linear density", "4", True),
         ("conversion factor to 1 kg", "1.0", True)]),
    ("401794bb-5de6-4ab1-b151-139135b4b9c9", "u-PVC window frame",
        [("area density", "4", True)]),  # already has linear density 2.8
    ("387f2ca0-04f7-443c-9a6d-2ecac4a8aefb", "Reinforcement steel wire",
        [("conversion factor to 1 kg", "1.0", True), ("linear density", "0.02", True)]),
    ("f86ba942-a418-40af-abc0-9155ae8a76fb", "Cement based plaster",
        [("conversion factor to 1 kg", "1.0", True)]),  # already has volume density 2200
]

_FLAG = "[best-effort estimate conversion(s) added 2026-07 — see backfill_epd_conversions]"


class Command(BaseCommand):
    help = "Add missing EPD conversion factors (additive, idempotent, corruption-aware)."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true",
                            help="Show what would change; write nothing.")

    def handle(self, *args, **options):
        dry = options["dry_run"]
        added = skipped = 0
        missing_epds = []

        with transaction.atomic():
            for epd_id, label, conv_specs in _PLAN:
                epd = EPD.objects.filter(pk=epd_id).first()
                if epd is None:
                    missing_epds.append((label, epd_id))
                    self.stdout.write(self.style.WARNING(
                        f"  EPD not on this DB, skipped: {label} ({epd_id})"))
                    continue

                conversions = list(epd.conversions or [])
                existing_names = {c.get("name") for c in conversions}
                any_estimate = False
                for name, value, is_estimate in conv_specs:
                    if name in existing_names:
                        skipped += 1
                        continue
                    conversions.append({
                        "name": name,
                        "unit": _UNIT[name],
                        "value": value,
                        "unit_description": _UNIT_DESC[name],
                    })
                    added += 1
                    any_estimate = any_estimate or is_estimate
                    tag = "EST" if is_estimate else "std"
                    self.stdout.write(
                        f"  {label}: + {name} = {value} {_UNIT[name]}  [{tag}]")

                if not dry:
                    epd.conversions = conversions
                    if any_estimate and _FLAG not in (epd.comment or ""):
                        epd.comment = ((epd.comment or "").strip() + " " + _FLAG).strip()
                    epd.save(update_fields=["conversions", "comment"])

            if dry:
                self.stdout.write(self.style.WARNING(
                    f"\n[DRY RUN] would add {added} conversion(s), "
                    f"{skipped} already present. No changes written."))
                transaction.set_rollback(True)
            else:
                self.stdout.write(self.style.SUCCESS(
                    f"\nDone: added {added} conversion(s), {skipped} already present."))
        if missing_epds:
            self.stdout.write(self.style.WARNING(
                f"{len(missing_epds)} target EPD(s) not found on this DB."))
