"""Seed the v1 example/reference buildings (prototype).

Creates, per data-rich cell (Homes: India/Indonesia/Cambodia; Office: India), two
read-only example buildings owned by a system account:
  * "Typical"    — a deep-copy of a representative real building from that cell
                   (anonymised: generic name, no owner/org), reflecting real practice.
  * "Low-carbon" — a copy of the Typical with masonry/cement/concrete swapped to
                   lower-carbon options where available for that country.

Idempotent: existing example buildings are removed and re-created on each run.

NOTE (prototype): "Typical" reuses a real building's structure for realism. For
production, HEAT should curate/authorise the source or author examples explicitly.
"""

import re

from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Count

from pages.models.building import Building, BuildingAssembly
from pages.models.assembly import Assembly, StructuralProduct
from pages.models.epd import EPD, EPDType
from pages.scripts.csv_import.utils import get_superuser
from pages.views.building.clone_building import clone_building, _LEAF_CHILD_MODELS
from pages.views.building.building_stats import calculate_total_embodied_carbon

# Plausible upfront embodied carbon per m2 (kgCO2e/m2) — used to reject source
# buildings with broken/zero/absurd data so examples are clean.
EC_MIN, EC_MAX = 50.0, 2500.0

# Placeholder / throwaway building names — de-preferred so a real-world named
# building (e.g. "Rumah Subsidi") wins over "B1"/"Building X" at equal fitness.
_PLACEHOLDER_RE = re.compile(
    r"^(building\s*[a-z]?|b\d+|bldg\.?\s*\d*|blg\s*\d*|\d+|test\s*\d*|sample|xyz|abc)$",
    re.IGNORECASE,
)


def _is_placeholder_name(name):
    return bool(_PLACEHOLDER_RE.match((name or "").strip()))


def _pick_representative(clean):
    """From [(building, ec), ...] pick the one nearest the cluster median carbon.

    Nearest-median gives a genuinely *typical* building rather than the richest
    outlier. A modest penalty de-prefers placeholder-named buildings.
    """
    ecs = sorted(ec for _, ec in clean)
    n = len(ecs)
    median_ec = ecs[n // 2] if n % 2 else (ecs[n // 2 - 1] + ecs[n // 2]) / 2

    def score(item):
        building, ec = item
        penalty = 0.15 * median_ec if _is_placeholder_name(building.name) else 0.0
        return abs(ec - median_ec) + penalty

    building, ec = min(clean, key=score)
    return building, ec, median_ec

# (building_type_label, category name in DB, country name)
CELLS = [
    ("Homes", "Homes", "India"),
    ("Homes", "Homes", "Indonesia"),
    ("Homes", "Homes", "Cambodia"),
    ("Office", "Office/Business", "India"),
]


def _find_lowcarbon_replacement(epd):
    """Return a lower-carbon generic EPD for the same country, or None to keep."""
    country = epd.country
    if country is None:
        return None
    name = (epd.name or "").lower()
    gen = EPD.objects.filter(country=country, type=EPDType.GENERIC)

    # Masonry walls -> cement-stabilised rammed earth (vernacular, all 5, m3, unit-safe)
    if any(k in name for k in ["brick", "block", "aac", "aerated", "masonry", "clinker"]):
        return (gen.filter(name__icontains="Cement-stabilised rammed earth").first())

    # Raw cement binder -> Portland slag cement (lower clinker) where a generic exists
    if "cement" in name and not any(
        k in name for k in ["mortar", "screed", "concrete", "fibre", "render", "plaster", "rammed"]
    ):
        return gen.filter(name__icontains="Portland slag cement").exclude(
            name__icontains="stabil"
        ).first()

    # Conventional ready-mix concrete -> fly-ash blend where a generic exists
    if any(k in name for k in ["ready mix", "ready-mix", " rmc", "concrete c", "m15", "m20", "m25", "m30"]):
        return gen.filter(name__icontains="Ready mix concrete with fly-ash").first()

    return None


class Command(BaseCommand):
    help = "Seed v1 example/reference buildings (Typical + Low-carbon per data-rich cell)."

    def _delete_examples(self):
        """Delete all example buildings child-first.

        The building child FKs (EnergySummary etc.) are DEFERRABLE NO-ACTION at the
        DB level even though the ORM declares CASCADE, so a plain queryset
        ``.delete()`` leaves the OneToOne children dangling and fails at commit.
        We delete leaves -> assemblies -> buildings explicitly to be robust.
        """
        ex = list(Building.objects.filter(is_example=True).values_list("pk", flat=True))
        if not ex:
            return 0
        with transaction.atomic():
            asm_ids = list(
                BuildingAssembly.objects.filter(building_id__in=ex).values_list("assembly_id", flat=True)
            )
            for model in _LEAF_CHILD_MODELS:
                model.objects.filter(building_id__in=ex).delete()
            BuildingAssembly.objects.filter(building_id__in=ex).delete()
            StructuralProduct.objects.filter(assembly_id__in=asm_ids).delete()
            Assembly.objects.filter(pk__in=asm_ids).delete()
            Building.objects.filter(pk__in=ex).delete()
        return len(ex)

    def handle(self, *args, **options):
        # NOTE: not wrapped in a single atomic block — candidate carbon checks below
        # read structural data and must not share a transaction with the writes
        # (a caught calc error would otherwise poison the whole reseed). Each
        # clone_building() is atomic on its own.
        system_user = get_superuser()

        # Idempotent: wipe existing examples first.
        removed = self._delete_examples()
        self.stdout.write(self.style.WARNING(f"Removed {removed} existing example building(s)."))

        for label, cat_name, country_name in CELLS:
            candidates = (
                Building.objects.filter(
                    category__category__name=cat_name,
                    country__name=country_name,
                    is_example=False,
                )
                .annotate(n=Count("buildingassembly__assembly__structuralproduct"))
                .filter(n__gt=0)
                .order_by("-n")[:25]
            )
            # Keep only buildings whose embodied carbon is plausible (clean data),
            # then pick the one nearest the cluster median (a *typical* building,
            # not the richest outlier).
            clean = []
            for c in candidates:
                try:
                    ec = float(calculate_total_embodied_carbon(c, simulated=False))
                except Exception:
                    continue
                if EC_MIN <= ec <= EC_MAX:
                    clean.append((c, ec))
            if not clean:
                self.stdout.write(self.style.ERROR(
                    f"  {label} — {country_name}: no representative building with clean data, skipped."
                ))
                continue
            src, src_ec, median_ec = _pick_representative(clean)

            # Typical
            typ = clone_building(
                src, system_user,
                new_name=f"Typical {label} — {country_name} (example)",
                as_example=True, variant=Building.EXAMPLE_TYPICAL,
            )
            # Low-carbon = copy of Typical, then swap materials
            low = clone_building(
                typ, system_user,
                new_name=f"Low-carbon {label} — {country_name} (example)",
                as_example=True, variant=Building.EXAMPLE_LOW_CARBON,
            )
            swaps = 0
            for sp in StructuralProduct.objects.filter(
                assembly__buildingassembly__building=low
            ).select_related("epd", "epd__country"):
                repl = _find_lowcarbon_replacement(sp.epd)
                if repl and repl.id != sp.epd_id:
                    sp.epd = repl
                    sp.save(update_fields=["epd"])
                    swaps += 1

            self.stdout.write(self.style.SUCCESS(
                f"  {label} — {country_name}: '{src.name}' "
                f"(EC={src_ec:.0f}, median={median_ec:.0f}, rows={src.n}) "
                f"-> Typical + Low-carbon ({swaps} material swaps)."
            ))

        self.stdout.write(self.style.SUCCESS(f"Total example buildings now: {Building.objects.filter(is_example=True).count()}"))
