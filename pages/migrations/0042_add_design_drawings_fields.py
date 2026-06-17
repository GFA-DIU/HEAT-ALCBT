from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("pages", "0041_add_seismic_zone_to_building"),
    ]

    operations = [
        migrations.AddField(
            model_name="building",
            name="has_design_drawings",
            field=models.BooleanField(default=False, verbose_name="Has Design Drawings"),
        ),
        migrations.AlterField(
            model_name="building",
            name="has_boq",
            field=models.BooleanField(default=False, verbose_name="Has Bill of Quantities (BoQ)"),
        ),
        migrations.AddField(
            model_name="buildingboqfile",
            name="file_type",
            field=models.CharField(
                choices=[("boq", "Bill of Quantities"), ("drawing", "Design Drawing")],
                default="boq",
                max_length=10,
                verbose_name="File Type",
            ),
        ),
    ]
