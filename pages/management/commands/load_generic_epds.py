import os
import pandas as pd

from django.core.management.base import BaseCommand
from django.db.models import Q
from django.contrib.auth import get_user_model
from cities_light.models import Country

from pages.models.epd import EPD, EPDImpact, EPDType, Impact, MaterialCategory


User = get_user_model()
superuser = User.objects.filter(is_superuser=True).order_by('date_joined').first() # Gets the first superuser on the deployment

class Command(BaseCommand):
    help = "Imports generic EPDs from a CSV file."

    def get_conversions(self, row):
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


    def add_impacts(self, row, epd):
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

    def handle(self, *args, **options):
        
        file_path = "pages/data/generic_EPDs.csv"
        
        try:
            df = pd.read_csv(file_path, sep=';')
        except Exception as e:
            self.stderr.write(f"Error reading CSV file: {e}")
            return
        # Iterate through each row and access the data

        for index, row in df.iterrows():
            self.stdout.write(f"Row {index} is being processed.")
            try:
                conversions = self.get_conversions(row)
                if not pd.isna(row["level_2_index"]):
                    if len(str(row["level_2_index"])) == 1:
                        level_2_index = f"0{row["level_2_index"]}"
                    else:
                        level_2_index = str(row["level_2_index"])
                    category_id = f"{row["level_0_index"]}.{row["level_1_index"]}.{level_2_index}"
                    category, _ = MaterialCategory.objects.get_or_create(
                        category_id=category_id, level=3
                    )
                new_epd = EPD(
                    country=Country.objects.get(
                        Q(name=row["country"])
                        | Q(code2=row["country"])
                        | Q(code3=row["country"])
                    ),
                    source="GFA-HEAT",
                    name=row["name"],
                    names=[
                        {"lang": "en", "value": row["name"]},
                        {"lang": "de", "value": row["name"]},
                    ],
                    public=True,
                    conversions=conversions,
                    category=category,
                    declared_unit=row["declared_unit"],
                    type=EPDType.GENERIC,
                    declared_amount=1,
                    comment=f"Created based on (ÖkobdautURL+UUID)", 
                    created_by_id=superuser.id, 
                )
                new_epd.save()
                self.add_impacts(row, new_epd)
                self.stdout.write(f"Row {index} processed.")
            except Exception as e:
                self.stderr.write(f"Error in row {index}: {e}")