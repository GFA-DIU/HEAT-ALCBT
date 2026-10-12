"""Read-only snapshot of the database, for before and after a deployment.

Writes nothing. Run it against production before merging, keep the output, run
it again afterwards and compare. If a number moves that the runbook did not say
would move, you know immediately rather than after someone reports it.

    heroku run python manage.py preflight_deploy_check --app <app>

The expected "after" figures are in docs/deploy_epd_operational_batch.md.
"""
from django.core.management.base import BaseCommand
from django.db import connection
from django.db.models import Count

from pages.models.building import Building
from pages.models.building_operation.energy_summary import EnergySummary
from pages.models.epd import EPD, EPDLabel

ALCBT = ["India", "Thailand", "Vietnam", "Indonesia", "Cambodia"]


class Command(BaseCommand):
    help = "Read-only pre/post-deployment snapshot. Writes nothing."

    def handle(self, *args, **opts):
        w = self.stdout.write

        w(self.style.MIGRATE_HEADING("\n== schema =="))
        with connection.cursor() as c:
            c.execute(
                "SELECT name FROM django_migrations WHERE app='pages' "
                "ORDER BY id DESC LIMIT 1")
            row = c.fetchone()
        w("  latest pages migration   %s" % (row[0] if row else "none"))
        # the four fields this batch adds; absent before the deploy
        for model, field in ((EPD, "material_name"), (EPD, "source_name")):
            present = field in [f.name for f in model._meta.get_fields()]
            w("  EPD.%-22s %s" % (field, "present" if present else "absent"))

        w(self.style.MIGRATE_HEADING("\n== EPD catalogue =="))
        w("  EPDs total               %d" % EPD.objects.count())
        w("  EPDs ALCBT               %d"
          % EPD.objects.filter(country__name__in=ALCBT).count())
        w("  from environdec library  %d"
          % EPD.objects.filter(source__icontains="environdec.com/library").count())
        try:
            w("  with material_name       %d"
              % EPD.objects.exclude(material_name__isnull=True).count())
        except Exception:
            w("  with material_name       n/a (field not deployed yet)")
        w("  declared_amount = 0      %d  (these return None, not a crash)"
          % EPD.objects.filter(declared_amount=0).count())

        w(self.style.MIGRATE_HEADING("\n== GCCA labels =="))
        bands = dict(EPDLabel.objects.values_list("score")
                     .annotate(n=Count("id")).order_by())
        w("  labels total             %d" % EPDLabel.objects.count())
        w("  bands                    %s" % bands)
        stale = bands.get("G", 0)
        if stale:
            w(self.style.WARNING(
                "  %d label(s) scored 'G' - a band the corrected AA-F scale does\n"
                "    not define. They render a broken image until\n"
                "    apply_gcca_concrete_labels --overwrite has run." % stale))

        w(self.style.MIGRATE_HEADING("\n== operational =="))
        w("  buildings                %d" % Building.objects.count())
        w("  energy summaries         %d" % EnergySummary.objects.count())
        try:
            from pages.models.building_operation.ventilation import (
                VentilationSystem, VentilationType)
            cass = VentilationSystem.objects.filter(
                ventilation_type=VentilationType.CASSETTE_AC)
            w("  cassette AC under vent   %d records / %d buildings"
              % (cass.count(), cass.values("building").distinct().count()))
            w("    these report as cooling after the deploy; no total changes")
        except Exception as exc:
            w("  cassette check           n/a (%s)" % type(exc).__name__)

        w(self.style.SUCCESS("\nRead-only: nothing was written.\n"))
