"""Incident recovery: restore structural assemblies lost from specific buildings.

Background (2026-07): six buildings owned by expert@greenbuildingpartner.com lost
most/all of their structural assemblies on the live database (an isolated incident
on that one account — no other users were affected, verified by a local-vs-prod
diff). The pre-loss structural definitions were preserved in the local backbone
and bundled here as JSON. This command re-creates the MISSING assemblies on
whichever database it runs against.

Safety properties:
  * ADDITIVE ONLY — it never deletes or edits existing rows. Assemblies already
    present on the target (matched by name per building) are left untouched, so
    survivors are not duplicated and nothing live is overwritten.
  * IDEMPOTENT — re-running only adds what is still missing (by name).
  * VALIDATED — a product is only created if its EPD id exists on the target DB;
    a classification is only linked if it exists, else left null. Missing EPDs are
    logged and that product is skipped (never a broken FK).
  * TRANSACTIONAL — all writes happen in one transaction; any error rolls back.
  * --dry-run prints exactly what would be added and writes nothing.

Usage:
    python manage.py restore_lost_assemblies --dry-run
    python manage.py restore_lost_assemblies
"""

import json
import os
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction

from pages.models.assembly import (Assembly, AssemblyCategoryTechnique,
                                    AssemblyMode, StructuralProduct)
from pages.models.building import Building, BuildingAssembly
from pages.models.epd import EPD

_DATA_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),  # pages/
    "data", "restore_lost_assemblies.json",
)


class Command(BaseCommand):
    help = "Restore structural assemblies lost from specific buildings (additive, idempotent)."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true",
                            help="Show what would be added; write nothing.")

    def handle(self, *args, **options):
        dry = options["dry_run"]
        with open(_DATA_FILE, encoding="utf-8") as f:
            source = json.load(f)

        total_asm = total_prod = total_skipped_epd = 0

        with transaction.atomic():
            for building_id, bdata in source.items():
                building = Building.objects.filter(pk=building_id).first()
                if building is None:
                    self.stdout.write(self.style.WARNING(
                        f"  building {building_id} not found on this DB — skipped."))
                    continue

                existing_names = set(
                    BuildingAssembly.objects.filter(building=building)
                    .values_list("assembly__name", flat=True)
                )
                to_add = [a for a in bdata["assemblies"] if a["name"] not in existing_names]
                if not to_add:
                    self.stdout.write(f"  {bdata['name']}: nothing missing (already complete).")
                    continue

                added_here = prod_here = 0
                for a in to_add:
                    # Validate products' EPDs first; skip products with a missing EPD.
                    valid_products = []
                    for p in a["products"]:
                        if p["epd_id"] and EPD.objects.filter(pk=p["epd_id"]).exists():
                            valid_products.append(p)
                        else:
                            total_skipped_epd += 1
                            self.stdout.write(self.style.WARNING(
                                f"    EPD not on this DB, product skipped: {p.get('epd_name')} ({p['epd_id']})"))

                    if dry:
                        added_here += 1
                        prod_here += len(valid_products)
                        continue

                    # NB: classification lives on StructuralProduct, not Assembly.
                    asm = Assembly.objects.create(
                        created_by=building.created_by,
                        name=a["name"],
                        comment=a.get("comment") or "",
                        dimension=a["dimension"],
                        mode=AssemblyMode.CUSTOM,
                        is_boq=a.get("is_boq", False),
                        is_template=False,
                        public=False,
                        draft=False,
                    )
                    for p in valid_products:
                        p_cls = p["classification_id"] if p["classification_id"] and \
                            AssemblyCategoryTechnique.objects.filter(pk=p["classification_id"]).exists() else None
                        StructuralProduct.objects.create(
                            assembly=asm,
                            epd_id=p["epd_id"],
                            quantity=Decimal(str(p["quantity"])),
                            input_unit=p["input_unit"],
                            description=p.get("description") or "",
                            classification_id=p_cls,
                        )
                        prod_here += 1
                    BuildingAssembly.objects.create(
                        building=building,
                        assembly=asm,
                        quantity=Decimal(str(a["ba_quantity"])),
                        reporting_life_cycle=a.get("reporting_life_cycle") or 50,
                    )
                    added_here += 1

                total_asm += added_here
                total_prod += prod_here
                self.stdout.write(self.style.SUCCESS(
                    f"  {bdata['name']}: {'would add' if dry else 'added'} "
                    f"{added_here} assemblies / {prod_here} products."))

            if dry:
                self.stdout.write(self.style.WARNING(
                    f"\n[DRY RUN] would add {total_asm} assemblies / {total_prod} products "
                    f"({total_skipped_epd} products skipped for missing EPD). No changes written."))
                transaction.set_rollback(True)
            else:
                self.stdout.write(self.style.SUCCESS(
                    f"\nDone: added {total_asm} assemblies / {total_prod} products "
                    f"({total_skipped_epd} products skipped for missing EPD)."))
