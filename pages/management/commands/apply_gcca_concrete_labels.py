"""Compute and apply GCCA A–G concrete Low Carbon Ratings dynamically.

Rates ready-mix / precast STRUCTURAL concrete (declared per m³, with a parseable
compressive strength class) from its GWP A1–A3, using pages/scripts/Label_mapping/
gcca_rating.py. Additive by default: only EPDs that don't already carry a GCCA
label are rated, so existing curated labels are left untouched. Idempotent.

Skips (left unrated), per agreed scope:
  - non-structural products (cement, AAC, mortar, grout, primer, pipe…): no
    parseable strength class -> skipped automatically;
  - strengths outside the GCCA table (Thai 180/210 KSC ≈ M16, or M45);
  - strength ranges ("200–300 KSC");
  - implausible GWP (<50 kgCO₂e/m³) — data anomalies.
"""
import logging

from django.core.management.base import BaseCommand
from django.db.models import Q

from pages.models.epd import EPD, EPDLabel, Label, Unit
from pages.scripts.Label_mapping.gcca_rating import strength_to_mxx, rate

logger = logging.getLogger(__name__)

LABEL_NAME = "GCCA Global Reference Threshold Low Carbon and Near Zero Emissions Concrete"
MIN_SANE_GWP = 50.0  # kgCO₂e/m³ — below this a per-m³ concrete value is bad data


class Command(BaseCommand):
    help = "Compute & apply GCCA A–G ratings to ready-mix/precast concrete EPDs."

    def add_arguments(self, parser):
        parser.add_argument(
            "--source", type=str, default=None,
            help="Limit to one source (e.g. TGO). Default: all sources.",
        )
        parser.add_argument(
            "--overwrite", action="store_true",
            help="Re-rate EPDs that already have a GCCA label (default: only add new).",
        )
        parser.add_argument(
            "--dry-run", action="store_true",
            help="Show what would change without writing.",
        )

    def handle(self, *args, **options):
        label, _ = Label.objects.get_or_create(
            name=LABEL_NAME,
            defaults={"scale_parameters": ["A", "B", "C", "D", "E", "F", "G"]},
        )

        qs = EPD.objects.filter(declared_unit=Unit.M3).filter(
            Q(name__icontains="concrete") | Q(name__icontains="beton")
        )
        if options["source"]:
            qs = qs.filter(source=options["source"])
        if not options["overwrite"]:
            qs = qs.exclude(epdlabel__label=label)

        rated = skipped = 0
        by_band = {}
        skip_examples = []
        for epd in qs.iterator():
            mxx = strength_to_mxx(epd.name)
            if mxx is None:
                skipped += 1
                if len(skip_examples) < 12:
                    skip_examples.append(f"{epd.name[:55]} (no in-table strength)")
                continue
            try:
                gwp = float(epd.get_gwp_impact_sum("a1a3") or 0) if epd.declared_amount else 0.0
            except ArithmeticError:
                gwp = 0.0
            if gwp < MIN_SANE_GWP:
                skipped += 1
                if len(skip_examples) < 12:
                    skip_examples.append(f"{epd.name[:55]} (gwp anomaly: {gwp})")
                continue
            band = rate(gwp, mxx)
            by_band[band] = by_band.get(band, 0) + 1
            if not options["dry_run"]:
                EPDLabel.objects.update_or_create(
                    epd=epd, label=label, defaults={"score": band}
                )
            rated += 1

        prefix = "[DRY-RUN] " if options["dry_run"] else ""
        self.stdout.write(self.style.SUCCESS(
            f"{prefix}Rated {rated} concrete EPDs; skipped {skipped}."
        ))
        self.stdout.write(f"  Band distribution: {dict(sorted(by_band.items()))}")
        if skip_examples:
            self.stdout.write("  Sample skipped:")
            for s in skip_examples:
                self.stdout.write(f"    - {s}")
