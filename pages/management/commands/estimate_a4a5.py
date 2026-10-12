"""Estimate A4 (transport) + A5w (construction waste) upfront carbon for a building.

Read-only preview — writes nothing. Lets you try the A4/A5 methodology locally on
any existing building before the UI/persistence is wired in.

    python manage.py estimate_a4a5 --building <id-or-prefix>
    python manage.py estimate_a4a5 --building <id> --scenario national   # force a scenario

Reuses the existing A1–A3 engine (calculate_impacts) for mass + A1–A3, then applies
the country/RICS defaults in pages/scripts/a4a5/. All figures are kg CO2e per m².
"""
from decimal import Decimal

from django.core.management.base import BaseCommand

from pages.models.building import Building, BuildingAssembly
from pages.views.building.impact_calculation import (
    calculate_impacts, ImpactCalculationError)
from pages.scripts.a4a5.compute import material_a4_a5


class Command(BaseCommand):
    help = "Preview A4 + A5w upfront carbon (kg CO2e/m²) for a building. Read-only."

    def add_arguments(self, parser):
        parser.add_argument("--building", required=True, help="Building id or id prefix.")
        parser.add_argument("--scenario", choices=["local", "national", "imported"],
                            help="Force a sourcing scenario for every material (else per-category default).")

    def handle(self, *args, **opts):
        b = Building.objects.filter(id__startswith=opts["building"]).first()
        if not b:
            self.stdout.write(self.style.ERROR(f"No building matching '{opts['building']}'."))
            return
        floor_area = float(b.total_floor_area or 0)
        country_name = getattr(getattr(b, "country", None), "name", None) or "?"
        force = opts.get("scenario")

        self.stdout.write(self.style.SUCCESS(
            f"\nBuilding: {b.name}  |  country: {country_name}  |  GFA: {floor_area:g} m²"
            + (f"  |  forced scenario: {force}" if force else "")))
        self.stdout.write(f"{'Material':38} {'cat':16} {'A1-A3':>9} {'A4':>8} {'A5w':>8} {'scenario':10} {'w%':>4}")
        self.stdout.write("-" * 100)

        tot = {"a1a3": Decimal("0"), "a4": Decimal("0"), "a5w": Decimal("0")}
        skipped = 0

        for ba in b.buildingassembly_set.all():
            assembly = ba.assembly
            for p in assembly.structuralproduct_set.all():
                try:
                    impacts = calculate_impacts(
                        dimension=assembly.dimension,
                        assembly_quantity=ba.quantity,
                        total_floor_area=floor_area,
                        p=p,
                    )
                except (ImpactCalculationError, ValueError, AttributeError, ZeroDivisionError):
                    skipped += 1
                    continue

                a1a3 = next((Decimal(str(i["impact_value"])) for i in impacts
                             if i["impact_type"].impact_category == "gwp"
                             and i["impact_type"].life_cycle_stage == "a1a3"
                             and Decimal(str(i["impact_value"])) > 0), Decimal("0"))
                mass_kg = next((i.get("mass_kg") for i in impacts), None)
                cat = p.epd.category
                cat_name = (getattr(cat, "name_en", None) or getattr(cat, "name", None)
                            or (str(cat) if cat else "")) if cat else ""

                a4, a5w, meta = material_a4_a5(
                    a1a3_per_m2=a1a3, mass_kg=mass_kg, floor_area=floor_area,
                    country_name=country_name, category_name=cat_name, scenario=force)

                tot["a1a3"] += a1a3; tot["a4"] += a4; tot["a5w"] += a5w
                self.stdout.write(
                    f"{(p.epd.name or '')[:37]:38} {cat_name[:15]:16} "
                    f"{float(a1a3):9.2f} {float(a4):8.3f} {float(a5w):8.3f} "
                    f"{meta['scenario']:10} {meta['waste_rate']*100:3.0f}")

        up = tot["a1a3"] + tot["a4"] + tot["a5w"]
        self.stdout.write("-" * 100)
        self.stdout.write(self.style.SUCCESS(
            f"{'TOTAL (kg CO2e/m²)':55} A1-A3={float(tot['a1a3']):.1f}  "
            f"A4={float(tot['a4']):.2f}  A5w={float(tot['a5w']):.2f}  → Upfront A1-A5={float(up):.1f}"))
        if floor_area:
            self.stdout.write(
                f"A4 = {float(tot['a4']/up*100 if up else 0):.1f}% of upfront; "
                f"A5w = {float(tot['a5w']/up*100 if up else 0):.1f}%")
        if skipped:
            self.stdout.write(self.style.WARNING(f"{skipped} product(s) skipped (unresolved A1–A3)."))
