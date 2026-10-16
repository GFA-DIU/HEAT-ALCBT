"""Recompute chiller annual energy, undoing the import's chiller-count factor.

Why these are wrong
-------------------
`_calc_chiller_energy` in the Excel importer multiplied the plant energy by the
number of chillers, while the form on screen does not. The form is right: its
own tooltip says "the plant energy comes from the total cooling load above,
which already covers all machines", so `total_cooling_load` is the whole
plant's load and multiplying by the machine count counts the plant once per
machine.

The same building entered by hand and by import therefore disagreed by the
chiller count - a 15-chiller plant imported at 945,000 kWh/yr against 63,000
entered manually.

    python manage.py recalc_chiller_energy --dry-run
    python manage.py recalc_chiller_energy

Safe to re-run: it recomputes from the stored inputs rather than dividing the
stored result, so a record already correct is left as it is.
"""
from decimal import Decimal

from django.core.management.base import BaseCommand

from pages.models.building_operation.chilling import CoolingSystemChiller


class Command(BaseCommand):
    help = ("Recompute chiller annual energy from the stored inputs, without "
            "the importer's chiller-count factor.")

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true",
                            help="Report what would change and write nothing.")
        parser.add_argument("--tolerance", type=float, default=0.5,
                            help="kWh difference below which a record counts "
                                 "as already correct (default 0.5).")

    def handle(self, *args, **opts):
        w = self.stdout.write
        rows = CoolingSystemChiller.objects.select_related("building").all()
        w("chiller records: %d" % rows.count())

        changed, already_ok, incomplete = [], 0, 0
        for c in rows:
            expected = self._expected(c)
            if expected is None:
                incomplete += 1
                continue
            stored = Decimal(str(c.total_energy_consumption_kwh_per_year or 0))
            if abs(float(stored - expected)) <= opts["tolerance"]:
                already_ok += 1
                continue
            changed.append((c, stored, expected))

        w("  already correct     %d" % already_ok)
        w("  inputs incomplete   %d  (left alone)" % incomplete)
        w("  would change        %d" % len(changed))
        w("")

        for c, stored, expected in changed[:25]:
            factor = (float(stored / expected) if expected else 0)
            w("  %-34s chillers=%-3s  %12.0f -> %12.0f   (x%.2f)"
              % ((getattr(c.building, "name", "?") or "?")[:34],
                 c.number_of_chillers, stored, expected, factor))
        if len(changed) > 25:
            w("  ... and %d more" % (len(changed) - 25))

        if opts["dry_run"]:
            w(self.style.WARNING(
                "\nDry run - nothing written. Re-run without --dry-run to apply."))
            return

        for c, _stored, expected in changed:
            c.total_energy_consumption_kwh_per_year = expected
            c.save(update_fields=["total_energy_consumption_kwh_per_year"])
        w(self.style.SUCCESS("\nrecomputed %d record(s)." % len(changed)))
        if changed:
            w("Buildings holding these chillers need their EnergySummary "
              "recalculated before their dashboards agree.")

    @staticmethod
    def _expected(c):
        """The form's formula: load x efficiency x hours x days x weeks.

        No chiller count or automatic VSD/heat-recovery discounts.
        """
        def f(v):
            try:
                return Decimal(str(v or 0))
            except Exception:
                return Decimal("0")

        load = f(c.total_cooling_load_rt)
        eff = f(c.baseline_cooling_efficiency_kw_h)
        hrs = f(c.operation_hours_per_workday)
        days = f(c.workdays_per_week)
        weeks = f(c.workweeks_per_year)
        if min(load, eff, hrs, days, weeks) <= 0:
            return None

        return (load * eff * hrs * days * weeks).quantize(Decimal("0.001"))


def _yes(value):
    return str(value).strip().lower() in ("yes", "true", "1")
