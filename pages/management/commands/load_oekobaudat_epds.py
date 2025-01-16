from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model

from cities_light.models import Country

from pages.scripts.oekobaudat.oekobaudat_loader import (
    get_all_epds,
    get_full_epd,
    parse_epd,
)

from pages.models.epd import (
    EPD,
    EPDType,
    MaterialCategory,
    EPDImpact,
    Impact,
    INDICATOR_UNIT_MAPPING,
)


class Command(BaseCommand):
    help = "Load all EPDs from Ökobaudat database."

    def handle(self, *args, **options):
        # load EPD data
        uuids = get_all_epds()

        for uuid in uuids:
            data = get_full_epd(uuid)
            epd = parse_epd(data)
            self.stdout.write(self.style.SUCCESS(("Starting %s", epd)))
            store_epd(epd)
            self.stdout.write(self.style.SUCCESS(("Successfully uploaded %s", uuid)))


def store_epd(epd_data: dict):
    """
    Parse the EPD data and link it to the correct material categories and impacts.
    """
    # Step 1: Retrieve the MaterialCategory based on levels
    classification = MaterialCategory.objects.get(
        category_id=epd_data.get("classification")
    )
    country = Country.objects.get(name="Germany")
    User = get_user_model()
    superuser = User.objects.filter(is_superuser=True).first()

    # Step 2: Create or update the EPD record
    epd, created = EPD.objects.update_or_create(
        UUID=epd_data["uuid"],
        defaults={
            "name": epd_data["name"],
            "names": epd_data.get("names"),
            "declared_unit": epd_data["declared_unit"],
            "conversions": epd_data["conversions"],
            "category": classification,
            "source": epd_data["source"],
            "type": EPDType.OFFICAL,
            "country": country,
            "declared_amount": epd_data["declared_amount"],
            "version": epd_data["version"],
            # from base
            "created_by": superuser,
            "public": True,
            "draft": False,
        },
    )

    print("EPD %s", epd)
    print("Created %s", created)

    # Step 3: Parse and link environmental impacts
    for key, value in epd_data.items():
        if key.startswith("gwp") or key.startswith("penrt"):
            if value is not None:
                # Extract impact category and life cycle stage
                impact_category_key = key.split("_")[0]  # e.g., 'gwp'
                life_cycle_stage_key = key.split("_")[1]  # e.g., 'a1a3'

                # Retrieve or create the Impact instance
                impact, _ = Impact.objects.get_or_create(
                    impact_category=impact_category_key,
                    life_cycle_stage=life_cycle_stage_key,
                    unit=INDICATOR_UNIT_MAPPING.get(impact_category_key),  # Default unit, update as needed
                )

                # Create or update the EPDImpact linking table
                EPDImpact.objects.update_or_create(
                    epd=epd, impact=impact, defaults={"value": value}
                )
    return epd
