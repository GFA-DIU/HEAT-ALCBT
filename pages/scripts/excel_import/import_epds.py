import pandas as pd

from pages.models.epd import EPD, EPDType
from pages.scripts.excel_import.utils import add_impacts, get_category, get_conversions, get_country, get_superuser


impact_columns = [
    "penrt_a1a3 [MJ]",
    "penrt_c3 [MJ]",
    "penrt_c4 [MJ]",
    "penrt_d [MJ]",
    "gwp_a1a3 [kgCo2e]",
    "gwp_c3  [kgCo2e]",
    "gwp_c4 [kgCo2e]",
    "gwp_d  [kgCo2e]",
]


def import_EDGE_EPDs():
    file_path = "pages/data/EDGE_HANDBOOK_EPDs.csv"
    df = pd.read_csv(file_path, sep=";")

    superuser = get_superuser()
    # Iterate through each row and access the data

    for index, row in df.iterrows():
        print(f"Row {index} is being processed.")
        try:
            conversions = get_conversions(row)
            
            new_epd = EPD(
                country=get_country(row["country"]),
                source=row["source"],
                name=row["name"],
                names=[
                    {"lang": "en", "value": row["name"]},
                ],
                public=True,
                conversions=conversions,
                category=get_category(row),
                declared_unit=row["declared_unit"],
                type=EPDType.OFFICIAL,
                declared_amount=1,
                comment=row["description"],
                created_by_id=superuser.id, 
            )
            new_epd.save()
            add_impacts(row, new_epd, impact_columns)
            print(f"Row {index} processed.")
        except Exception as e:
            print(f"Error in row {index}:")
            print(e)
