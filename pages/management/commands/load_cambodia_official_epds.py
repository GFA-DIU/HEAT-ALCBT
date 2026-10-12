"""Load the six official Cambodian cement EPDs into the EPD database.

Cambodia carried a single official (manufacturer) EPD against 178 derived
generics. Six verified declarations exist in the project EPD library; this adds
the five that were missing and renames the existing one so the two Chip Mong
INSEE products can be told apart.

    python manage.py load_cambodia_official_epds --dry-run
    python manage.py load_cambodia_official_epds

Idempotent - keyed on (name, country), so re-running updates rather than
duplicates. Values are read from pages/data/cambodia_official_epds.csv, which
was transcribed from the EPD PDFs themselves.
"""
import logging

from django.core.management.base import BaseCommand
from django.db import transaction

from pages.models.epd import EPD, EPDType
from pages.scripts.csv_import.import_cambodia_official_epds import (
    RENAME_EXISTING,
    import_cambodia_official_epds,
)
from pages.scripts.csv_import.utils import get_country


class Command(BaseCommand):
    help = "Load the six official Cambodian cement EPDs."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run", action="store_true",
            help="Show what would change and roll back without writing.",
        )

    def handle(self, *args, **opts):
        logging.basicConfig(level=logging.INFO, format="  %(message)s", force=True)
        country = get_country("Cambodia")

        before = list(
            EPD.objects.filter(country=country, type=EPDType.OFFICIAL)
            .values_list("name", flat=True).order_by("name")
        )
        self.stdout.write(f"Cambodian official EPDs before: {len(before)}")
        for n in before:
            self.stdout.write(f"    {n}")
        self.stdout.write("")

        try:
            with transaction.atomic():
                import_cambodia_official_epds()

                after = list(
                    EPD.objects.filter(country=country, type=EPDType.OFFICIAL)
                    .values_list("name", flat=True).order_by("name")
                )
                # A renamed record is not a new one; label it accurately so the
                # operator running this against production is not misled.
                renamed_to = set(RENAME_EXISTING.values())
                self.stdout.write("")
                self.stdout.write(f"Cambodian official EPDs after: {len(after)}")
                for n in after:
                    if n in before:
                        marker = ""
                    elif n in renamed_to:
                        marker = "  <- renamed, same record"
                    else:
                        marker = "  <- new"
                    self.stdout.write(f"    {n}{marker}")

                if opts["dry_run"]:
                    raise _Rollback()
        except _Rollback:
            self.stdout.write(self.style.WARNING(
                "\nDry run - rolled back, nothing written. Re-run without --dry-run to apply."))
            return

        self.stdout.write(self.style.SUCCESS("\nDone."))


class _Rollback(Exception):
    """Internal: unwinds the transaction after a dry run."""
