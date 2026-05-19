from django.core.management.base import BaseCommand
from django.db import transaction

from pages.scripts.csv_import.update_epd_names import update_epd_names


class Command(BaseCommand):
    help = "Update EPD names from docs/ALL EPDs.xlsx mapped correct names"

    @transaction.atomic
    def handle(self, *args, **options):
        self.stdout.write("Starting EPD name update...")
        update_epd_names(self.stdout, self.style)
        self.stdout.write(self.style.SUCCESS("Done."))
