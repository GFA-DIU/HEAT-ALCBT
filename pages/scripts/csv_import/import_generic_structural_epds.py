import logging
import pandas as pd

from pages.models.epd import EPD, EPDType, MaterialCategory
from pages.scripts.csv_import.utils import (
    add_impacts,
    get_conversions,
    get_country,
    get_superuser,
)

logger = logging.getLogger(__name__)

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


def get_category(row):
    if not pd.isna(row["level_2_index"]):
        if len(str(row["level_2_index"])) == 1:
            level_2_index = f"0{row['level_2_index']}"
        else:
            level_2_index = str(row["level_2_index"])
        category_id = f"{row['level_0_index']}.{row['level_1_index']}.{level_2_index}"
        category, _ = MaterialCategory.objects.get_or_create(
            category_id=category_id, level=3
        )
        return category

def import_generic_structural_epds():
    file_path = "pages/data/generic_EPDs.csv"
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

            new_epd = EPD(
                country=get_country(row["country"]),
                source="GFA-HEAT",
                name=row["name"],
                names=[{"lang": "en", "value": row["name"]}],
                public=True,
                conversions=conversions,
                category=get_category(row),
                declared_unit=row["declared_unit"],
                type=EPDType.GENERIC,
                declared_amount=row["declared_amount"],
                comment=f"Created based on {row['UUID']} (https://oekobaudat.de/OEKOBAU.DAT/datasetdetail/process.xhtml?uuid={row['UUID']})",
                created_by_id=superuser.id,
            )
            new_epd.save()
            add_impacts(row, new_epd, impact_columns)
            # print(f"Row {index} processed.")
            success += 1

        except Exception as e:
            logger.exception("Error in row %s", index)
            failure += 1
            failure_list.append(index)
            raise Exception(f"Error in row {index}: {e}\n  Row: {row}")

    if failure == 0:
        print(
            f"\033[32mSuccessfully uploaded {success} generic EPDs. Errors occured in {failure} cases. Rows: {failure_list}"
        )
    else:
        print(
            f"Successfully uploaded {success} generic EPDs. Errors occured in {failure} cases. Rows: {failure_list}"
        )
