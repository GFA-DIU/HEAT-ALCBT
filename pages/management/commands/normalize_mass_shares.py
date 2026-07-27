"""Repair corrupted share-of-mass / share-of-volume percentages.

Background: the structural importer labelled each material in a mass/volume
assembly with input_unit=PERCENT ("share of mass/volume") but stored the source
spreadsheet's RAW quantity (a mass/volume), not a 0-100 share. So the shares in
many assemblies sum to thousands of percent (e.g. a single material at 372116%),
which fails the "shares must sum to 100%" check and makes those materials get
SKIPPED in the carbon calculation.

The material mass used by the calc is `assembly_quantity × (share / 100)` — i.e.
the share is only the SPLIT between materials; the real total is the assembly
quantity. So the correct repair is to normalise each assembly's percent shares to
sum to 100% (each value ÷ Σ values × 100). This preserves the mass ratio between
materials and turns single-material assemblies into 100% (discarding the junk raw
value, which was never a valid share).

Safety:
  * Only touches assemblies whose percent shares do NOT already sum to 100%
    (idempotent — correct assemblies are left untouched; re-runs are no-ops).
  * Only rewrites StructuralProduct.quantity for input_unit=PERCENT rows.
  * Transactional; --dry-run prints the plan and writes nothing.
  * Logs a sample of before→after so the change is auditable.

Usage:
    python manage.py normalize_mass_shares --dry-run
    python manage.py normalize_mass_shares
"""

from collections import defaultdict
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction

from pages.models.assembly import StructuralProduct
from pages.models.epd import Unit

_HUNDRED = Decimal("100")


class Command(BaseCommand):
    help = "Normalise corrupted share-of-mass/volume percentages to sum to 100% (additive-safe, idempotent)."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true",
                            help="Show what would change; write nothing.")

    def handle(self, *args, **options):
        dry = options["dry_run"]

        # Group percent products by assembly and sum their shares.
        by_assembly = defaultdict(list)
        for sp in StructuralProduct.objects.filter(input_unit=Unit.PERCENT).select_related("assembly"):
            by_assembly[sp.assembly_id].append(sp)

        to_fix = {}
        for aid, sps in by_assembly.items():
            total = sum(Decimal(str(sp.quantity)) for sp in sps)
            if total > 0 and round(total, 4) != _HUNDRED:
                to_fix[aid] = (sps, total)

        self.stdout.write(
            f"Assemblies with percent shares: {len(by_assembly)} | "
            f"not summing to 100% (to fix): {len(to_fix)}"
        )

        samples = 0
        fixed_asm = fixed_prod = 0
        with transaction.atomic():
            for aid, (sps, total) in to_fix.items():
                # Quantize each share to the field's 2 decimals, then push the tiny
                # rounding residual onto the largest share so the total is exactly
                # 100.00 (the calc validates round(sum, 4) == 100).
                shares = [[sp, (Decimal(str(sp.quantity)) / total * _HUNDRED).quantize(Decimal("0.01"))]
                          for sp in sps]
                residual = _HUNDRED - sum(s for _, s in shares)
                if residual != 0:
                    largest = max(range(len(shares)), key=lambda i: shares[i][1])
                    shares[largest][1] += residual
                for sp, new in shares:
                    if samples < 12:
                        self.stdout.write(
                            f"  asm={str(aid)[:8]} '{sp.assembly.name[:22]}' "
                            f"{sp.epd.name[:20] if sp.epd else '?'}: {sp.quantity} -> {new}%"
                        )
                        samples += 1
                    if not dry:
                        sp.quantity = new
                        sp.save(update_fields=["quantity"])
                    fixed_prod += 1
                fixed_asm += 1

            if dry:
                self.stdout.write(self.style.WARNING(
                    f"\n[DRY RUN] would normalise {fixed_prod} products across {fixed_asm} assemblies. "
                    "No changes written."))
                transaction.set_rollback(True)
            else:
                self.stdout.write(self.style.SUCCESS(
                    f"\nDone: normalised {fixed_prod} products across {fixed_asm} assemblies."))
