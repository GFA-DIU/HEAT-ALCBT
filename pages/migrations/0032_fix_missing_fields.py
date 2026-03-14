"""
Migration to reconcile live-DB schema differences with Django ORM state.

- number_of_stars on HotWaterSystem: never existed in live DB — state-only removal
- assembly draft/public help_text: columns exist, type unchanged — state-only alter
- country FK on CategorySubcategory: already handled by 0012 — no action needed here
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('cities_light', '0011_alter_city_country_alter_city_region_and_more'),
        ('pages', '0031_assembly_template_fields'),
        ('pages', '0031_merge_20260305_2157'),
    ]

    operations = [
        # number_of_stars was removed from the model but never existed in the
        # live DB — only update Django's migration state.
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.RemoveField(
                    model_name='hotwatersystem',
                    name='number_of_stars',
                ),
            ],
        ),

        # draft/public help_text change on Assembly — state-only.
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.AlterField(
                    model_name='assembly',
                    name='draft',
                    field=models.BooleanField(default=False, help_text='Whether this assembly is in draft state'),
                ),
                migrations.AlterField(
                    model_name='assembly',
                    name='public',
                    field=models.BooleanField(default=False, help_text='Whether this template is publicly accessible'),
                ),
            ],
        ),
    ]
