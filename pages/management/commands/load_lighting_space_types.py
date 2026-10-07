"""Load the lighting space types and each country's reference values.

Replaces the old six-option room list, which was the same for every building
and drove nothing in the calculation.

Where the values come from
--------------------------
Indonesia  SNI 6197:2020 - the only standard of the five that publishes both
           illuminance and LPD per room. 99 rows consolidated to 63: nine
           spaces that SNI repeats verbatim across building types (toilet,
           stairs, kitchen, cafeteria ...) become one "common" entry each, and
           eleven retail stores that all share LPD 10.76 become two.
Vietnam    QCVN 09:2017/BXD Table 2.5 - whole-building LPD only, 11 building
           types. No per-room value exists.
Thailand   Building Energy Code, Ministerial Regulation B.E. 2563 (2020) -
           whole-building LPD only, three groups.
India      ECBC 2017 publishes ~58 space functions, but its two-column table
           layout mis-pairs values under text extraction, so nothing is loaded
           here until each number is checked against the source PDF.
Cambodia   Deliberately empty. Cambodia has no building energy code - its own
           National Energy Efficiency Policy 2022-2030 says so - and a code is
           still in development. BEAT shows no benchmark rather than inventing
           one or borrowing a neighbour's.

    python manage.py load_lighting_space_types --dry-run
    python manage.py load_lighting_space_types
"""
import csv
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction

from pages.models.building_operation.lighting import (
    LightingReference, LightingSpaceType, RoomType,
)
from pages.scripts.csv_import.utils import get_country

CSV_PATH = "pages/data/lighting_space_types.csv"

# QCVN 09:2017/BXD Table 2.5 - whole-building LPD, W/m2, mapped onto BEAT's
# building categories.
VIETNAM_BUILDING_LPD = {
    "Office": 11, "Office/Business": 11,
    "Hotels": 11, "Hospitality": 11, "Resorts": 11,
    "Healthcare": 13, "Health care": 13,
    "Education": 12, "Educational": 12,
    "Retail": 16, "Shopping complex": 16,
    "Apartments": 8, "Homes": 8,
}

# Thailand BEC, Ministerial Regulation B.E. 2563 (2020): three groups.
THAILAND_BUILDING_LPD = {
    "Office": 10, "Office/Business": 10, "Education": 10, "Educational": 10,
    "Retail": 11, "Shopping complex": 11, "Assembly": 11,
    "Hotels": 12, "Hospitality": 12, "Resorts": 12,
    "Healthcare": 12, "Health care": 12, "Apartments": 12,
}

# The original six options. Kept so the ~490 existing records still show a
# label, but hidden when adding a new lighting system.
LEGACY = [
    (RoomType.OFFICE_CONFERENCE, "Office: Conference Room"),
    (RoomType.HOSPITAL_PATIENT, "Hospital: Patient Room"),
    (RoomType.RESIDENTIAL_KITCHEN, "Residential: Kitchen"),
    (RoomType.RESIDENTIAL_DINING, "Residential: Dining Room"),
    (RoomType.COMMERCIAL_GENERAL, "Commercial: General Office/Retail"),
    (RoomType.COMMERCIAL_MALL, "Commercial: Mall / Department Store"),
]


def _dec(v):
    v = (v or "").strip()
    return Decimal(v) if v else None


def _int(v):
    v = (v or "").strip()
    return int(float(v)) if v else None


class Command(BaseCommand):
    help = "Load lighting space types and national reference LPD values."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true",
                            help="Show what would change and roll back.")

    def handle(self, *args, **opts):
        try:
            with transaction.atomic():
                self._load()
                if opts["dry_run"]:
                    raise _Rollback()
        except _Rollback:
            self.stdout.write(self.style.WARNING(
                "\nDry run - rolled back, nothing written."))
            return
        self.stdout.write(self.style.SUCCESS("\nDone."))

    def _load(self):
        # --- space types -------------------------------------------------
        created = updated = 0
        with open(CSV_PATH, newline="", encoding="utf-8") as fh:
            rows = list(csv.DictReader(fh))

        for r in rows:
            cats = [c.strip() for c in (r["building_categories"] or "").split(",") if c.strip()]
            _, was_new = LightingSpaceType.objects.update_or_create(
                code=r["code"],
                defaults={
                    "name": r["name"],
                    "is_common": r["is_common"].strip().upper() == "TRUE",
                    "building_categories": cats,
                    "sort_order": int(r["sort_order"]),
                    "legacy": False,
                },
            )
            created += was_new
            updated += (not was_new)

        for code, label in LEGACY:
            LightingSpaceType.objects.update_or_create(
                code=code,
                defaults={"name": label, "is_common": False,
                          "building_categories": [], "legacy": True,
                          "sort_order": 900},
            )

        common = LightingSpaceType.objects.filter(is_common=True, legacy=False).count()
        specific = LightingSpaceType.objects.filter(is_common=False, legacy=False).count()
        self.stdout.write(
            f"space types: {created} created, {updated} updated "
            f"({common} common + {specific} building-specific, {len(LEGACY)} legacy kept)")

        # --- Indonesia: per-room references -------------------------------
        indonesia = get_country("Indonesia")
        LightingReference.objects.filter(country=indonesia).delete()
        n = 0
        for r in rows:
            st = LightingSpaceType.objects.get(code=r["code"])
            lpd, lux = _dec(r["id_lpd"]), _int(r["id_lux"])
            if lpd is None and lux is None:
                continue
            LightingReference.objects.create(
                country=indonesia, space_type=st,
                basis=LightingReference.Basis.ROOM,
                lpd_w_m2=lpd, lux=lux,
                standard="SNI 6197:2020",
                notes=(r.get("notes") or "")[:255] or None,
            )
            n += 1
        self.stdout.write(f"Indonesia: {n} per-room references (SNI 6197:2020)")

        # --- Vietnam / Thailand: whole-building references -----------------
        for cname, table, standard in [
            ("Vietnam", VIETNAM_BUILDING_LPD, "QCVN 09:2017/BXD Table 2.5"),
            ("Thailand", THAILAND_BUILDING_LPD,
             "Building Energy Code, Ministerial Regulation B.E. 2563 (2020)"),
        ]:
            country = get_country(cname)
            LightingReference.objects.filter(country=country).delete()
            for cat, lpd in table.items():
                LightingReference.objects.create(
                    country=country, building_category=cat,
                    basis=LightingReference.Basis.BUILDING,
                    lpd_w_m2=Decimal(str(lpd)), standard=standard,
                    notes="Whole-building average, not a per-room limit.",
                )
            self.stdout.write(
                f"{cname}: {len(table)} whole-building references ({standard.split(',')[0]})")

        # --- India / Cambodia ---------------------------------------------
        self.stdout.write(
            "India: none loaded - ECBC 2017 has ~58 space functions but its "
            "two-column tables mis-pair under extraction; verify against the PDF first")
        self.stdout.write(
            "Cambodia: none by design - no national building energy code exists")


class _Rollback(Exception):
    """Internal: unwinds the transaction after a dry run."""
