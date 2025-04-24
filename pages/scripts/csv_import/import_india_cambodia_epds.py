import pandas as pd

from pages.models.epd import EPD, EPDType
from pages.scripts.csv_import.utils import (
    add_impacts,
    get_conversions,
    get_country,
    get_superuser,
    get_category
)

import logging
# Configure the logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)  # or the appropriate level for your use case

# Create a console handler with a specific log level
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.DEBUG)

# Create a formatter and add it to the handler
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
console_handler.setFormatter(formatter)

# Add the handler to the logger
logger.addHandler(console_handler)


impact_columns = [
    "penrt_a1a3 [MJ]",
    "penrt_c3 [MJ]",
    "penrt_c4 [MJ]",
    "penrt_d [MJ]",
    "gwp_a1a3 [kgCo2e]",
    "gwp_c3 [kgCo2e]",
    "gwp_c4 [kgCo2e]",
    "gwp_d [kgCo2e]",
]

def import_india_and_cambodia_epds():
    file_path = "pages/data/India_and_Cambodia_updated_20250424.csv"
    superuser = get_superuser()

    try:
        df = pd.read_csv(file_path, sep=";")
    except Exception as e:
        print(f"Error reading CSV file: {e}")
        return

    # Iterate through each row and access the data
    success = 0
    failure = 0
    failure_list = []
    for index, row in df.iterrows():
        print(f"Row {index} is being processed.")
        try:
            conversions = get_conversions(row)
            declared_amount = row.get("declared_amount", 1.0)
            if pd.isna(declared_amount):
                declared_amount = 1.0
            
            new_epd, created = EPD.objects.update_or_create(
                country=get_country(row["country"]),
                source=row["source"],
                name=row["name"],
                public=True,
                created_by_id=superuser.id,
                defaults={
                    "names": [{"lang": "en", "value": row["name"]}],
                    "conversions": conversions,
                    "category": get_category(row),
                    "declared_unit": row["declared_unit"],
                    "type": EPDType.OFFICIAL,
                    "declared_amount": declared_amount,  
                    "UUID": row["epd identifier"]
                }
            )
            if created:
                logger.info("Created EPD %s", new_epd)
            else:
                logger.info("Updated EPD %s", new_epd)
            add_impacts(row, new_epd, impact_columns)
            success += 1

        except Exception as e:
            logger.exception(f"Error in row {index}: {e}")
            failure += 1
            failure_list.append(index)

    if failure == 0:
        print(
            f"\033[32mSuccessfully uploaded {success} generic EPDs. Errors occured in {failure} cases. Rows: {failure_list}"
        )
    else:
        print(
            f"Successfully uploaded {success} generic EPDs. Errors occured in {failure} cases. Rows: {failure_list}"
        )
