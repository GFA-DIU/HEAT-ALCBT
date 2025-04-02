import os
import django
import sys

# Set up Django settings
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "django_project.settings")
django.setup()

import pandas as pd

from cities_light.models import Country
from django.contrib.auth import get_user_model
from pages.models.epd import EPD, EPDImpact, EPDType, Impact, MaterialCategory
from django.db.models import Q


def get_conversions(row):
    conversions = []
    if not pd.isna(row["weight [kg]"]):
        conversions.append(
            {
                "name": "conversion factor to 1 kg",
                "unit": "-",  # following the practice in Ökobaudat, see PR #116.
                "value": str(row["weight [kg]"]),
                "unit_description": "Without unit",
            }
        )
    if not pd.isna(row["volume density [kg/m3]"]):
        conversions.append(
            {
                "name": "volume density",
                "unit": "kg/m^3",
                "value": str(row["volume density [kg/m3]"]),
                "unit_description": "kilograms per cubic metre",
            }
        )
    if not pd.isna(row["area density [kg/m2]"]):
        conversions.append(
            {
                "name": "area density",
                "unit": "kg/m^2",
                "value": str(row["area density [kg/m2]"]),
                "unit_description": "kilograms per square metre",
            }
        )
    if not pd.isna(row["linear density [kg/m]"]):
        conversions.append(
            {
                "name": "linear density",
                "unit": "kg/m",
                "value": str(row["linear density [kg/m]"]),
                "unit_description": "kilograms per metre",
            }
        )
    return conversions


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

def add_impacts(row, epd):
    for col in impact_columns:
        # Only process if the value is not NaN
        if pd.isna(row[col]):
            continue
        
        # Split the column name to extract the impact category and life cycle stage.
        # "penrt_a1a3 [MJ]" -> "penrt_a1a3" -> split by "_" gives ("penrt", "a1a3")
        impact_category, life_cycle_stage = col.split(" ")[0].split("_")
        
        # Get the impact object based on the extracted category and stage.
        impact = Impact.objects.get(
            impact_category=impact_category,
            life_cycle_stage=life_cycle_stage
        )
        
        # Update or create the EPDImpact record.
        EPDImpact.objects.update_or_create(
            epd=epd,
            impact=impact,
            defaults={"value": row[col]}
        )


file_path = "pages/data/EDGE_HANDBOOK_EPDs.csv"
df = pd.read_csv(file_path)

User = get_user_model()
superuser = User.objects.filter(is_superuser=True).order_by('date_joined').first() # Gets the first superuser on the deployment

# Iterate through each row and access the data

for index, row in df.iterrows():
    print(f"Row {index} is being processed.")
    try:
        conversions = get_conversions(row)
        if not pd.isna(row["level_2_index"]):
            category, _ = MaterialCategory.objects.get_or_create(
                category_id=row["level_2_index"], level=3
            )
        new_epd = EPD(
            country=Country.objects.get(
                Q(name=row["country"])
                | Q(code2=row["country"])
                | Q(code3=row["country"])
            ),
            source=row["source"],
            name=row["name"],
            names=[
                {"lang": "en", "value": row["name"]},
            ],
            public=True,
            conversions=conversions,
            category=category,
            declared_unit=row["declared_unit"],
            type=EPDType.OFFICIAL,
            declared_amount=1,
            comment=row["description"],
            created_by_id=superuser.id, 
        )
        new_epd.save()
        add_impacts(row, new_epd)
        print(f"Row {index} processed.")
    except Exception as e:
        print(f"Error in row {index}:")
        print(e)
