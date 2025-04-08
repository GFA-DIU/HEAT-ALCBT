from django.core.management.base import BaseCommand

from pages.scripts.csv_import.import_generic_operational_epds import import_generic_operational_epds
from pages.scripts.csv_import.import_generic_structural_epds import (
    import_generic_structural_epds,
)
from pages.scripts.csv_import.import_edge_handbook_epds import import_EDGE_EPDs


local_epd_files = {
    "EDGE_HANDBOOK_EPDs": import_EDGE_EPDs,
    "generic_EPDs": import_generic_structural_epds,
    "generic_operationaL_EPDs": import_generic_operational_epds
}


class Command(BaseCommand):
    help = "Load all EPDs from local Csv files in `pages/data/` to the database."

    def handle(self, *args, **options):
        for k, v in local_epd_files.items():
            self.stdout.write(self.style.SUCCESS(("Starting", k)))
            v()
            self.stdout.write(self.style.SUCCESS(("Successfully uploaded", k)))
