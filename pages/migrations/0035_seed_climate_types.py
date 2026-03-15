from django.db import migrations

CLIMATE_TYPES = [
    ("hot-dry", "A hot and dry climate with low humidity and high temperatures."),
    ("warm-humid", "A warm and humid climate with high moisture levels year-round."),
    ("composite", "A composite climate with mixed hot-dry and warm-humid conditions."),
    ("temperate", "A temperate climate with moderate temperatures and seasonal variation."),
    ("cold", "A cold climate with low temperatures and significant winter periods."),
    ("tropical-wet", "A tropical wet climate with high temperatures and heavy rainfall."),
]


def seed_climate_types(apps, schema_editor):
    ClimateType = apps.get_model("pages", "ClimateType")
    for name, description in CLIMATE_TYPES:
        ClimateType.objects.get_or_create(name=name, defaults={"description": description})


def unseed_climate_types(apps, schema_editor):
    ClimateType = apps.get_model("pages", "ClimateType")
    ClimateType.objects.filter(name__in=[name for name, _ in CLIMATE_TYPES]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("pages", "0034_add_climate_type_model"),
    ]

    operations = [
        migrations.RunPython(seed_climate_types, reverse_code=unseed_climate_types),
    ]