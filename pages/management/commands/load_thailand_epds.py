from django.core.management.base import BaseCommand
from django.db import transaction

from pages.scripts.csv_import.import_thailand_epds import import_thailand_epds


class Command(BaseCommand):
    help = "Load Thailand TGO CFP EPDs from TH_CFP_Final_Usable_Dataset_20260709.xlsx"

    @transaction.atomic
    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS("Starting Thailand TGO EPD import..."))
        import_thailand_epds()
        self.stdout.write(self.style.SUCCESS("Done."))
