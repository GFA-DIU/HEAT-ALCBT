from django.core.management.base import BaseCommand
from django.db import transaction

from pages.scripts.csv_import.update_generic_epd_gwp import update_generic_epd_gwp


class Command(BaseCommand):
    help = "Update gwp_a1a3 values for generic EPDs from docs/2026-02-19 - Template_Generic_EPD_CORRECTED.xlsx"

    @transaction.atomic
    def handle(self, *args, **options):
        self.stdout.write("Starting generic EPD GWP update...")
        update_generic_epd_gwp(self.stdout, self.style)
        self.stdout.write(self.style.SUCCESS("Done."))
