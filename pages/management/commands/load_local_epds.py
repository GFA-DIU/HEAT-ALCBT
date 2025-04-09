from django.db import transaction
from django.core.management.base import BaseCommand

from pages.scripts.csv_import.import_generic_operational_epds import (
    import_generic_operational_epds,
)
from pages.scripts.csv_import.import_generic_structural_epds import (
    import_generic_structural_epds,
)
from pages.scripts.csv_import.import_edge_handbook_epds import import_EDGE_EPDs
from pages.scripts.csv_import.import_india_cambodia_epds import import_epds


local_epd_files = {
    "EDGE_HANDBOOK_EPDs": import_EDGE_EPDs,
    "generic_EPDs": import_generic_structural_epds,
    "india_cambodia_EPDs_20250324": import_epds,
    "generic_operationaL_EPDs": import_generic_operational_epds
}


class Command(BaseCommand):
    help = "Load all EPDs from local Csv files in `pages/data/` to the database."

    @transaction.atomic
    def handle(self, *args, **options):
        for k, v in local_epd_files.items():
            self.stdout.write(self.style.SUCCESS(("Starting", k)))
            v()
            self.stdout.write(self.style.SUCCESS(("Successfully uploaded", k)))
