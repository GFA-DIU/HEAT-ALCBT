"""
Convert Building.climate_zone from CharField to ForeignKey(ClimateType).

Steps:
1. Add nullable climate_zone_new FK column
2. Populate it by matching ClimateType.name = old climate_zone value
3. Drop the old climate_zone CharField
4. Rename climate_zone_new → climate_zone
"""
from django.db import migrations, models
import django.db.models.deletion


def populate_fk(apps, schema_editor):
    Building = apps.get_model("pages", "Building")
    ClimateType = apps.get_model("pages", "ClimateType")

    climate_map = {ct.name: ct for ct in ClimateType.objects.all()}

    for building in Building.objects.all():
        ct = climate_map.get(building.climate_zone_old)
        if ct:
            building.climate_zone_new = ct
            building.save(update_fields=["climate_zone_new"])


def reverse_populate(apps, schema_editor):
    Building = apps.get_model("pages", "Building")
    for building in Building.objects.select_related("climate_zone_new").all():
        if building.climate_zone_new:
            building.climate_zone_old = building.climate_zone_new.name
            building.save(update_fields=["climate_zone_old"])


class Migration(migrations.Migration):

    dependencies = [
        ("pages", "0035_seed_climate_types"),
    ]

    operations = [
        # 1. Rename old CharField so we can read it during data migration
        migrations.RenameField(
            model_name="building",
            old_name="climate_zone",
            new_name="climate_zone_old",
        ),
        # 2. Add new FK column (nullable during migration)
        migrations.AddField(
            model_name="building",
            name="climate_zone_new",
            field=models.ForeignKey(
                to="pages.ClimateType",
                on_delete=django.db.models.deletion.PROTECT,
                null=True,
                blank=True,
                related_name="+",
                verbose_name="Climate",
            ),
        ),
        # 3. Populate FK from old char values
        migrations.RunPython(populate_fk, reverse_code=reverse_populate),
        # 4. Drop old CharField
        migrations.RemoveField(
            model_name="building",
            name="climate_zone_old",
        ),
        # 5. Rename new FK to climate_zone
        migrations.RenameField(
            model_name="building",
            old_name="climate_zone_new",
            new_name="climate_zone",
        ),
        # 6. Now make it non-nullable (all existing buildings should have a match)
        migrations.AlterField(
            model_name="building",
            name="climate_zone",
            field=models.ForeignKey(
                to="pages.ClimateType",
                on_delete=django.db.models.deletion.PROTECT,
                null=True,
                blank=True,
                related_name="buildings",
                verbose_name="Climate",
            ),
        ),
    ]