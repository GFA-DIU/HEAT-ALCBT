from django.core.management.base import BaseCommand

from pages.models.building_operation.chilling import RefrigerantGWP
from pages.models.building_operation.air_conditioning import CoolingSystemAirConditioner
from pages.models.building_operation.chilling import CoolingSystemChiller


class Command(BaseCommand):
    help = "Backfill baseline_refrigerant_emission_factor (GWP) for existing cooling system records that have it as null."

    def handle(self, *args, **options):
        self._backfill(CoolingSystemChiller, "chillers")
        self._backfill(CoolingSystemAirConditioner, "air conditioners")

    def _backfill(self, model, label):
        records = model.objects.filter(baseline_refrigerant_emission_factor__isnull=True)
        count = records.count()

        if count == 0:
            self.stdout.write(self.style.SUCCESS(f"No {label} need backfilling."))
            return

        updated = 0
        skipped = 0

        for record in records:
            gwp = RefrigerantGWP.get_gwp(record.refrigerant_type)
            if gwp is not None:
                record.baseline_refrigerant_emission_factor = gwp
                model.objects.filter(pk=record.pk).update(
                    baseline_refrigerant_emission_factor=gwp
                )
                updated += 1
            else:
                skipped += 1
                self.stdout.write(
                    self.style.WARNING(
                        f"No GWP found for refrigerant type '{record.refrigerant_type}' "
                        f"on {label} id={record.pk} - skipped."
                    )
                )

        self.stdout.write(
            self.style.SUCCESS(
                f"{label.capitalize()}: {updated} records updated, {skipped} skipped (no GWP mapping found)."
            )
        )
