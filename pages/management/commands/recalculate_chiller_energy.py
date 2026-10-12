"""Recalculate stored chiller annual energy after the double-count fix.

Chiller energy was computed client-side as

    load x number_of_chillers x kW/RT x hours x days x weeks x VSD x HR

but `total_cooling_load_rt` is the load of the WHOLE plant, so multiplying by
the chiller count double-counted it. The formula is fixed in the template, but
values already written to `total_energy_consumption_kwh_per_year` do not correct
themselves - this command rewrites them.

Run the dry run first and check the table:

    python manage.py recalculate_chiller_energy --dry-run
    python manage.py recalculate_chiller_energy --apply

Only records whose stored value matches the old buggy formula are touched.
Anything manually entered, or already correct, is left alone and reported.
"""
from decimal import Decimal, InvalidOperation

from django.core.management.base import BaseCommand
from django.db import transaction

from pages.models.building_operation.chilling import CoolingSystemChiller

# Must mirror recalcChillerEnergy() in cooling-system.html
VSD_FACTOR = Decimal("0.80")
HR_FACTOR = Decimal("0.70")
# Stored values are rounded to 3 dp client-side; allow a little slack when
# deciding whether a row was produced by the old formula.
MATCH_TOLERANCE = Decimal("0.01")  # 1%


def _expected(c, include_unit_count):
    """Annual kWh per the formula, with or without the double-count."""
    try:
        load = Decimal(str(c.total_cooling_load_rt or 0))
        eff = Decimal(str(c.baseline_cooling_efficiency_kw_h or 0))
        hrs = Decimal(str(c.operation_hours_per_workday or 0))
        days = Decimal(str(c.workdays_per_week or 0))
        weeks = Decimal(str(c.workweeks_per_year or 0))
    except (InvalidOperation, TypeError):
        return None
    if min(load, eff, hrs, days, weeks) <= 0:
        return None
    value = load * eff * hrs * days * weeks
    if include_unit_count:
        value *= Decimal(str(c.number_of_chillers or 1))
    if c.variable_speed_drives:
        value *= VSD_FACTOR
    if c.heat_recovery_system:
        value *= HR_FACTOR
    return value


def _close(a, b):
    if a is None or b is None or b == 0:
        return False
    return abs(a - b) / b <= MATCH_TOLERANCE


class Command(BaseCommand):
    help = "Recalculate chiller annual energy after the double-count fix."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true",
                            help="Write the corrected values. Without this, nothing changes.")
        parser.add_argument("--dry-run", action="store_true",
                            help="Explicit no-op; the default behaviour.")

    def handle(self, *args, **opts):
        apply_changes = opts["apply"]
        rows = (CoolingSystemChiller.objects
                .select_related("building")
                .order_by("-number_of_chillers", "id"))

        hdr = f"{'id':>5} {'building':32} {'units':>5} {'stored':>14} {'correct':>14} {'factor':>7}  status"
        self.stdout.write(hdr)
        self.stdout.write("-" * len(hdr))

        to_fix, skipped, already_ok = [], [], []
        for c in rows:
            stored = c.total_energy_consumption_kwh_per_year
            stored = Decimal(str(stored)) if stored is not None else None
            buggy = _expected(c, include_unit_count=True)
            correct = _expected(c, include_unit_count=False)
            name = (c.building.name or "")[:32]

            if correct is None:
                status, bucket = "SKIP incomplete inputs", skipped
            elif stored is None:
                status, bucket = "SKIP no stored value", skipped
            elif _close(stored, correct):
                status, bucket = "already correct", already_ok
            elif _close(stored, buggy):
                status, bucket = "FIX double-counted", to_fix
            else:
                status, bucket = "SKIP manual/unrecognised", skipped
            bucket.append((c, correct))

            factor = (stored / correct) if (stored and correct) else Decimal(0)
            self.stdout.write(
                f"{c.id:>5} {name:32} {c.number_of_chillers:>5} "
                f"{(stored or 0):>14,.0f} {(correct or 0):>14,.0f} {factor:>6.1f}x  {status}"
            )

        self.stdout.write("")
        self.stdout.write(f"to fix: {len(to_fix)} | already correct: {len(already_ok)} | skipped: {len(skipped)}")

        if not apply_changes:
            self.stdout.write(self.style.WARNING(
                "\nDry run - nothing written. Re-run with --apply to write the corrected values."))
            return

        with transaction.atomic():
            for c, correct in to_fix:
                c.total_energy_consumption_kwh_per_year = correct.quantize(Decimal("0.001"))
                c.save(update_fields=["total_energy_consumption_kwh_per_year"])
        self.stdout.write(self.style.SUCCESS(f"\nUpdated {len(to_fix)} chiller record(s)."))
        self.stdout.write(
            "Building energy summaries recompute from these rows, so affected buildings "
            "will show the corrected operational carbon on next view.")
