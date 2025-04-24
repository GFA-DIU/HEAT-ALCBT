from django.db import transaction
from django.core.management.base import BaseCommand

from pages.scripts.csv_import.import_global_epds import import_global_epds
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
    "generic_operationaL_EPDs": import_generic_operational_epds,
    "ECO_Platform_Global_EPDs": import_global_epds,
    "India_and_Cambodia_updated_20250424": import_epds,
}


class Command(BaseCommand):
    help = "Load all EPDs from local Csv files in `pages/data/` to the database."

    def add_arguments(self, parser):
        parser.add_argument(
            "-f",
            "--file",
            type=str,
            help="Optional: Specify a single EPD file key to load",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        file_key = options.get("file")
        if file_key:
            if file_key not in local_epd_files:
                self.stdout.write(self.style.ERROR(f"Invalid file key: {file_key}"))
                self.stdout.write(
                    self.style.WARNING(
                        f"Available keys: {', '.join(local_epd_files.keys())}"
                    )
                )
                return
            self.stdout.write(self.style.SUCCESS(f"Starting {file_key}"))
            local_epd_files[file_key]()
            self.stdout.write(self.style.SUCCESS(f"Successfully uploaded {file_key}"))
        else:
            for k, v in local_epd_files.items():
                self.stdout.write(self.style.SUCCESS(("Starting", k)))
                v()
                self.stdout.write(self.style.SUCCESS(("Successfully uploaded", k)))
