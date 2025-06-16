from django.db import transaction
from django.core.management.base import BaseCommand

from pages.scripts.Label_mapping.GCCA_mapping import add_GCCA_labels


class Command(BaseCommand):
    help = "Map GCCA label info to EPDs from mapping in `pages/data/`."

    def add_arguments(self, parser):
        parser.add_argument(
            "-f",
            "--file",
            type=str,
            help="Optional: Specify a single EPD file key to load",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        try:
            add_GCCA_labels()
            self.stdout.write(self.style.SUCCESS(f"Successfully concluded mapping."))
        except:
            self.stdout.write(self.style.WARNING(f"Error in mapping."))