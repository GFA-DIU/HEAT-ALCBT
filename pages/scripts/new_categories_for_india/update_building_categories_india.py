import json
from django.db import transaction

from pages.models import (
    CategorySubcategory,
    BuildingCategory,
    BuildingSubcategory,
    Building
)
from cities_light.models import Country

file_path = "pages/fixtures/india_category_mapping.json"

# Load India Country and its buildings
india = Country.objects.get(name="India")
indian_buildings = Building.objects.filter(country=india)

# Load JSON
with open(file_path) as f:
    data = json.load(f)

# Wrap in a transaction for safety
with transaction.atomic():
    for item in data:
        # Extract old and new categories
        old_cat_name = item["old"]["category"]
        old_sub_name = item["old"]["sub_category"]

        new_cat_name = item["new"]["category"]
        new_sub_name = item["new"]["sub_category"]

        # Get the old CategorySubcategory
        try:
            old_cat_sub_cat = CategorySubcategory.objects.get(
                category__name=old_cat_name,
                subcategory__name=old_sub_name
            )
        except CategorySubcategory.DoesNotExist:
            print(f"Old CategorySubcategory not found: {old_cat_name} / {old_sub_name}")
            continue

        # Ensure new Category exists
        new_category, _ = BuildingCategory.objects.get_or_create(name=new_cat_name)

        # Ensure new Subcategory exists
        new_subcategory, _ = BuildingSubcategory.objects.get_or_create(name=new_sub_name)

        # Ensure new CategorySubcategory exists
        new_cat_sub_cat, _ = CategorySubcategory.objects.get_or_create(
            category=new_category,
            subcategory=new_subcategory,
            country=india
        )

        # Update all buildings in bulk
        buildings_to_update = indian_buildings.filter(category=old_cat_sub_cat)
        buildings_to_update.update(category=new_cat_sub_cat)

        print(f"Updated {buildings_to_update.count()} buildings: "
              f"{old_cat_name}/{old_sub_name} → {new_cat_name}/{new_sub_name}")
