import logging

import pandas as pd

from pages.models.epd import EPD, EPDType, MaterialCategory, Unit
from pages.scripts.csv_import.utils import (
    add_impacts,
    get_conversions,
    get_country,
    get_superuser,
)

logger = logging.getLogger(__name__)

impact_columns = [
    "penrt_b6 [MJ]",
    "gwp_b6 [kgCo2e]",
]

parent = MaterialCategory.objects.get(category_id="9.2", level=2, name_en="Energy carrier - delivery free user")

def get_category(row):
    if not pd.isna(row["level_2_index"]):
        if len(str(row["level_2_index"])) == 1:
            level_2_index = f"0{row['level_2_index']}"
        else:
            level_2_index = str(row["level_2_index"])
        category_id = f"{row['level_0_index']}.{row['level_1_index']}.{level_2_index}"
        category, _ = MaterialCategory.objects.get_or_create(
            category_id=category_id, level=3, parent=parent
        )
        return category


def get_comment(row):
    if not pd.isna(row["Source"]):
        return row["Source"]
    else:
        return f"Created based on {row['UUID']} (https://oekobaudat.de/OEKOBAU.DAT/datasetdetail/process.xhtml?uuid={row['UUID']})"


def import_generic_operational_epds():
    file_path = "pages/data/generic_operational_EPDs.csv"
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

            new_epd, created = EPD.objects.update_or_create(
                country=get_country(row["country"]),
                source="GFA-HEAT",
                name=row["name"],
                public=True,
                created_by_id=superuser.id,
                defaults={
                    "names": [{"lang": "en", "value": row["name"]}],
                    "conversions": get_conversions(row),
                    "category": get_category(row),
                    "declared_unit": Unit.KWH,  ## TODO check if really the case
                    "type": EPDType.GENERIC,
                    "declared_amount":1,  ## TODO check if really the case
                    "comment": get_comment(row),  ## TODO adapt GEG text
                }
            )
            if created:
                logger.info("Created EPD %s", new_epd)
            else:
                logger.info("Updated EPD %s", new_epd)

            add_impacts(row, new_epd, impact_columns)
            # print(f"Row {index} processed.")
            success += 1

        except Exception as e:
            logger.exception("Error in row %s", index)
            failure += 1
            failure_list.append(index)
            raise Exception(f"Error in row {index}: {e} \n  Row: {row}")

    if failure == 0:
        print(
            f"\033[32mSuccessfully uploaded {success} generic EPDs. Errors occured in {failure} cases. Rows: {failure_list}"
        )
    else:
        print(
            f"Successfully uploaded {success} generic EPDs. Errors occured in {failure} cases. Rows: {failure_list}"
        )
