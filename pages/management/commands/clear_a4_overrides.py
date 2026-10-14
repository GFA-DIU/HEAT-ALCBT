"""Clear per-material A4 distance / emission-factor overrides.

Why these exist
---------------
The Upfront panel used to stamp the scenario's default distance and emission
factor into the override boxes the moment the sourcing dropdown changed. Saving
then froze that copy onto the material, so the row stopped following the country
default without ever saying so. Every stored override found when this was
written matched its scenario's default exactly, which is the signature of the
prefill rather than of a deliberate choice.

Distance and emission factor are no longer editable per material — the sourcing
scenario picks the journey and the factors come from the country tables — so a
stored override now does nothing but silently contradict them.

    python manage.py clear_a4_overrides --dry-run
    python manage.py clear_a4_overrides

Safe to re-run. `sourcing_scenario` and `waste_rate` are deliberate user choices
and are never touched.
"""
from django.core.management.base import BaseCommand
from django.db.models import Q

from pages.models.assembly import StructuralProduct
from pages.scripts.a4a5 import defaults as D


class Command(BaseCommand):
    help = "Clear a4_distance_km / a4_ef overrides. Keeps scenario and waste rate."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true",
                            help="Report what would change and write nothing.")
        parser.add_argument("--all", action="store_true",
                            help="Clear every override, including any that does "
                                 "not match a scenario default (by default those "
                                 "are kept and listed, in case someone meant them).")

    def handle(self, *args, **opts):
        w = self.stdout.write
        rows = StructuralProduct.objects.filter(
            Q(a4_distance_km__isnull=False) | Q(a4_ef__isnull=False)
        ).select_related("assembly")

        total = rows.count()
        w("materials carrying an A4 override: %d" % total)
        if not total:
            w(self.style.SUCCESS("nothing to do."))
            return

        accidental, deliberate = [], []
        for sp in rows:
            country = self._country_of(sp)
            scen = sp.sourcing_scenario or "national"
            legs = D.scenario_legs(scen, country)
            default_km = D.scenario_total_km(legs)
            looks_prefilled = (
                sp.a4_distance_km is not None
                and abs(float(sp.a4_distance_km) - default_km) < 0.5)
            (accidental if looks_prefilled else deliberate).append(sp)

        w("  %d match a scenario default exactly (the prefill's signature)" % len(accidental))
        w("  %d do not" % len(deliberate))

        for sp in deliberate[:10]:
            w("     kept: %s  distance=%s ef=%s scenario=%s"
              % (str(sp.id)[:8], sp.a4_distance_km, sp.a4_ef, sp.sourcing_scenario))
        if len(deliberate) > 10:
            w("     ... and %d more" % (len(deliberate) - 10))

        targets = (accidental + deliberate) if opts["all"] else accidental
        if not targets:
            w(self.style.SUCCESS("nothing to clear."))
            return

        if opts["dry_run"]:
            w(self.style.WARNING(
                "\nDry run — would clear %d override(s), writing nothing." % len(targets)))
            return

        n = StructuralProduct.objects.filter(
            id__in=[sp.id for sp in targets]
        ).update(a4_distance_km=None, a4_ef=None)
        w(self.style.SUCCESS("\ncleared %d override(s)." % n))
        if deliberate and not opts["all"]:
            w("%d override(s) left alone; pass --all to clear those too."
              % len(deliberate))

    @staticmethod
    def _country_of(sp):
        for ba in sp.assembly.buildingassembly_set.all():
            c = getattr(ba.building, "country", None)
            if c is not None:
                return c.name
        return "?"
