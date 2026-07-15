import pandas as pd

from cities_light.models import Country
from django.db.models import Q
from django.contrib.auth import get_user_model
from django.contrib.auth.models import User

from pages.models.epd import INDICATOR_UNIT_MAPPING, EPDImpact, Impact, MaterialCategory


def get_conversions(row) -> list[dict]:
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


def add_impacts(row, epd, impact_columns) -> None:
    for col in impact_columns:
        # Only process if the value is not NaN
        if pd.isna(row[col]):
            continue

        # Split the column name to extract the impact category and life cycle stage.
        # "penrt_a1a3 [MJ]" -> "penrt_a1a3" -> split by "_" gives ("penrt", "a1a3")
        impact_category, life_cycle_stage = col.split(" ")[0].split("_")

        # Get the impact object based on the extracted category and stage.
        impact, _ = Impact.objects.get_or_create(
            impact_category=impact_category,
            life_cycle_stage=life_cycle_stage,
        )

        # Update or create the EPDImpact record.
        EPDImpact.objects.update_or_create(
            epd=epd, impact=impact, defaults={"value": row[col]}
        )


def get_country(country) -> Country:
    return Country.objects.get(Q(name=country) | Q(code2=country) | Q(code3=country))


def get_category(row) -> MaterialCategory:
    # Prefer the source's Ökobaudat classification id (level 3, else level 2).
    # Use an existing category only — do NOT get_or_create, which used to spawn
    # nameless placeholder rows when the id wasn't in our tree.
    for idx, level in ((row.get("level_2_index"), 3), (row.get("level_1_index"), 2)):
        if idx is not None and not pd.isna(idx):
            cat = MaterialCategory.objects.filter(category_id=idx, level=level).first()
            if cat:
                return cat
    # No valid classification id -> resolve by product name (shared resolver),
    # falling back to "Unknown" rather than an empty/placeholder category.
    from pages.scripts.epd_categorization import resolve_by_name, category_by_name

    return resolve_by_name(row.get("name")) or category_by_name("Unknown")


def get_superuser() -> User:
    User = get_user_model()
    return (
        User.objects.filter(is_superuser=True).order_by("date_joined").first()
    )  # Gets the first superuser on the deployment
