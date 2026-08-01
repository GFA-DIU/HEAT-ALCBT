"""Audit buildings for implausible embodied-carbon inputs/results.

Runs the shared plausibility checker (pages/views/building/plausibility.py) over
one building or all of them and prints a grouped report. Read-only — writes
nothing.

Usage:
    python manage.py check_building_plausibility --building <id-prefix>
    python manage.py check_building_plausibility               # all buildings
    python manage.py check_building_plausibility --errors-only  # hide warnings
"""

from collections import Counter

from django.core.management.base import BaseCommand

from pages.models.building import Building
from pages.views.building.plausibility import check_building


class Command(BaseCommand):
    help = "Report implausible embodied-carbon inputs/results across buildings (read-only)."

    def add_arguments(self, parser):
        parser.add_argument("--building", help="Only this building (id or id prefix).")
        parser.add_argument("--errors-only", action="store_true",
                            help="Show only error-level flags.")

    def handle(self, *args, **options):
        qs = Building.objects.all()
        if options["building"]:
            qs = qs.filter(id__startswith=options["building"])

        flagged = 0
        totals = Counter()
        for b in qs:
            flags = check_building(b)
            if options["errors_only"]:
                flags = [f for f in flags if f["level"] == "error"]
            if not flags:
                continue
            flagged += 1
            n_err = sum(f["level"] == "error" for f in flags)
            n_warn = sum(f["level"] == "warning" for f in flags)
            self.stdout.write(self.style.MIGRATE_HEADING(
                f"\n{b.name or b.pk}  [{str(b.pk)[:8]}]  — {n_err} error(s), {n_warn} warning(s)"))
            for f in flags:
                totals[f["code"]] += 1
                mark = self.style.ERROR("ERR ") if f["level"] == "error" else self.style.WARNING("warn")
                self.stdout.write(f"   [{mark}] {f['code']:22} {f['target'][:40]:41} {f['message']}")

        self.stdout.write(self.style.SUCCESS(
            f"\n{flagged} building(s) flagged. Flag totals by code:"))
        for code, n in totals.most_common():
            self.stdout.write(f"   {n:5}  {code}")
