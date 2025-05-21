import traceback
import logging

from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model

from cities_light.models import Country

from pages.scripts.oekobaudat.oekobaudat_loader import parse_epd, get_classification
from pages.scripts.ecoplatform.ecoplatform_loader import (
    get_all_uuids_ecoplatform,
    get_full_epd,
    country_list,
)

from pages.models.epd import (
    EPD,
    EPDType,
    MaterialCategory,
    EPDImpact,
    Impact,
    INDICATOR_UNIT_MAPPING,
)
from pages.scripts.utils import find_missing_uuids

logger = logging.getLogger(__name__)

User = get_user_model()
superuser = User.objects.filter(is_superuser=True).first()

class Command(BaseCommand):
    help = "Load all EPDs from Ökobaudat database."

    def handle(self, *args, **options):
        # Load EPD data
        epd_info = get_all_uuids_ecoplatform()
        uuids = list(epd_info.keys())
        logger.info("Found a total of %s ECO-Platform EPDs.", len(uuids))
        
        # Filter-out EPDs that already exist in DB
        filtered_uuids = find_missing_uuids(uuids, chunk_size=1000)
        filtered_epds = [(epd_info[id]["uri"], epd_info[id]["geo"]) for id in filtered_uuids]
        logger.info("Found %s new EPDs out of %s total.", len(uuids)-len(filtered_epds), len(uuids))
        self.stdout.write(self.style.HTTP_INFO(f"Found {len(filtered_epds)} new EPDs out of {len(uuids)} total."))

        uri_issue_list = []
        for uri, geo in filtered_epds:
            try:
                # Fetch related country
                country = Country.objects.get(code2=geo)
                
                # Retrieve and process EPD data
                self.stdout.write(self.style.SUCCESS(f"1. Load epd with URI {uri}"))
                data = get_full_epd(uri)
                self.stdout.write(self.style.SUCCESS(f"2. Parse for {data}"))
                epd = parse_epd(data)
                self.stdout.write(self.style.SUCCESS(f"3. Parsed data to epd: {epd}"))
                # Store processed EPD
                store_epd(epd, country, data)
                self.stdout.write(self.style.SUCCESS(f"4. Successfully uploaded {uri}"))
            except Country.DoesNotExist:
                self.stdout.write(self.style.ERROR(f"Country with code2={geo} does not exist."))
            # except Exception as e:
            #     uri_issue_list.append(uri)
            #     self.stdout.write(self.style.ERROR(f"An error occurred: {str(e)}"))
            #     # self.stdout.write(self.style.ERROR(traceback.format_exc()))
            except:
                uri_issue_list.append(uri)
                logger.exception("Except was triggered.")
                self.stdout.write(self.style.ERROR(f"Except triggered An error occurred"))
                pass
                

        self.stdout.write(self.style.ERROR(f"List of problem uris: {uri_issue_list}"))
        
def store_epd(epd_data: dict, country: Country, data: dict):
    """
    Parse the EPD data and link it to the correct material categories and impacts.
    """
    try:
        classification = MaterialCategory.objects.get(
            category_id=epd_data.get("classification")
        )
    except MaterialCategory.DoesNotExist:
        try:
            classification_info = data["processInformation"]["dataSetInformation"].get(
                "classificationInformation"
            )
            if classification_info:
                classification = MaterialCategory.objects.get(
                    name_en="Primer for paints and plasters"
                )
            else:
                classification = MaterialCategory.objects.get(name_en="Unknown")
        except MaterialCategory.DoesNotExist:
            classification = None  # Or handle this case as neede

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
            "type": EPDType.OFFICIAL,
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
                )

                # Create or update the EPDImpact linking table
                EPDImpact.objects.update_or_create(
                    epd=epd, impact=impact, defaults={"value": value}
                )
    return epd


