import os
import django
import sys

# Ensure the script knows where the Django project is
sys.path.append(
    "/home/ramon/Desktop/GFA/D2/BEAT/HEAT-ALCBT"
)  # Change this to your actual project root

# Set up Django settings
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "django_project.settings")
django.setup()

import pandas as pd

from cities_light.models import Country
from accounts.models import CustomUser
from pages.models.epd import EPD, EPDImpact, EPDType, Impact, MaterialCategory
from django.db.models import Q


def get_conversions(row):
    conversions = []
    if not pd.isna(row["weight [kg]"]):
        conversions.append(
            {
                "name": "weight",
                "unit": "kg",
                "value": str(row["weight [kg]"]),
                "unit_description": "-",
            }
        )
    if not pd.isna(row["volume density [kg/m3]"]):
        conversions.append(
            {
                "name": "volume density",
                "unit": "kg/m^3",
                "value": str(row["volume density [kg/m3]"]),
                "unit_description": "-",
            }
        )
    if not pd.isna(row["area density [kg/m2]"]):
        conversions.append(
            {
                "name": "area density",
                "unit": "kg/m^2",
                "value": str(row["area density [kg/m2]"]),
                "unit_description": "-",
            }
        )
    if not pd.isna(row["linear density [kg/m]"]):
        conversions.append(
            {
                "name": "linear density",
                "unit": "kg/m",
                "value": str(row["linear density [kg/m]"]),
                "unit_description": "-",
            }
        )
    return conversions


def add_impacts(row, epd):
    if not pd.isna(row["penrt_a1a3 [MJ]"]):
        impact = Impact.objects.get(impact_category="penrt", life_cycle_stage="a1a3")
        EPDImpact.objects.update_or_create(
            epd=epd, impact=impact, defaults={"value": row["penrt_a1a3 [MJ]"]}
        )
        epd.impacts.add()
    if not pd.isna(row["penrt_c3 [MJ]"]):
        impact = Impact.objects.get(impact_category="penrt", life_cycle_stage="c3")
        EPDImpact.objects.update_or_create(
            epd=epd, impact=impact, defaults={"value": row["penrt_c3 [MJ]"]}
        )
    if not pd.isna(row["penrt_c4 [MJ]"]):
        impact = Impact.objects.get(impact_category="penrt", life_cycle_stage="c4")
        EPDImpact.objects.update_or_create(
            epd=epd, impact=impact, defaults={"value": row["penrt_c4 [MJ]"]}
        )
    if not pd.isna(row["penrt_d [MJ]"]):
        impact = Impact.objects.get(impact_category="penrt", life_cycle_stage="d")
        EPDImpact.objects.update_or_create(
            epd=epd, impact=impact, defaults={"value": row["penrt_d [MJ]"]}
        )
    if not pd.isna(row["gwp_a1a3 [kgCo2e]"]):
        impact = Impact.objects.get(impact_category="gwp", life_cycle_stage="a1a3")
        EPDImpact.objects.update_or_create(
            epd=epd, impact=impact, defaults={"value": row["gwp_a1a3 [kgCo2e]"]}
        )
    if not pd.isna(row["gwp_c3  [kgCo2e]"]):
        impact = Impact.objects.get(impact_category="gwp", life_cycle_stage="c3")
        EPDImpact.objects.update_or_create(
            epd=epd, impact=impact, defaults={"value": row["gwp_c3  [kgCo2e]"]}
        )
    if not pd.isna(row["gwp_c4 [kgCo2e]"]):
        impact = Impact.objects.get(impact_category="gwp", life_cycle_stage="c4")
        EPDImpact.objects.update_or_create(
            epd=epd, impact=impact, defaults={"value": row["gwp_c4 [kgCo2e]"]}
        )
    if not pd.isna(row["gwp_d  [kgCo2e]"]):
        impact = Impact.objects.get(impact_category="gwp", life_cycle_stage="d")
        EPDImpact.objects.update_or_create(
            epd=epd, impact=impact, defaults={"value": row["gwp_d  [kgCo2e]"]}
        )


file_path = "/home/ramon/Desktop/GFA/D2/BEAT/HEAT-ALCBT/pages/scripts/excel_import/edge_handbook_data.csv"
df = pd.read_csv(file_path)
sum = 0
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
            source="https://edgebuildings.com/wp-content/uploads/2022/04/IFC-India-Construction-Materials-Database-Methodology-Report.pdf",
            name=row["name"],
            names=[
                {"lang": "en", "value": row["name"]},
                {"lang": "de", "value": row["name"]},
            ],
            public=True,
            conversions=conversions,
            category=category,
            declared_unit=row["declared_unit"],
            type=EPDType.OFFICIAL,
            declared_amount=1,
        )
        new_epd.save()
        impacts = add_impacts(row, new_epd)
        print(f"Row {index} processed.")
    except Exception as e:
        print(f"Error in row {index}:")
        print(e)
