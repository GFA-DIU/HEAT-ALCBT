"""
Migration to reconcile live-DB schema differences with Django ORM state.

- number_of_stars on HotWaterSystem: never existed in live DB — state-only removal
- assembly draft/public help_text: columns exist, type unchanged — state-only alter
- country FK on CategorySubcategory: already exists in live DB (added manually
  before migrations tracked it). Use IF NOT EXISTS DDL so migration is safe to
  run on live DB (no-op) AND on fresh test DBs (creates the column).
"""
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('cities_light', '0011_alter_city_country_alter_city_region_and_more'),
        ('pages', '0031_assembly_template_fields'),
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

        # country FK on CategorySubcategory.
        # Live DB already has the column — IF NOT EXISTS makes this a no-op there.
        # Fresh test DBs will have the column created by this migration.
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunSQL(
                    sql="""
                        ALTER TABLE pages_categorysubcategory
                        ADD COLUMN IF NOT EXISTS country_id integer
                        REFERENCES cities_light_country(id)
                        DEFERRABLE INITIALLY DEFERRED;
                        CREATE INDEX IF NOT EXISTS pages_categorysubcategory_country_id_idx
                        ON pages_categorysubcategory (country_id);
                    """,
                    reverse_sql="""
                        DROP INDEX IF EXISTS pages_categorysubcategory_country_id_idx;
                        ALTER TABLE pages_categorysubcategory DROP COLUMN IF EXISTS country_id;
                    """,
                ),
            ],
            state_operations=[
                migrations.AddField(
                    model_name='categorysubcategory',
                    name='country',
                    field=models.ForeignKey(
                        blank=True,
                        help_text='Leave blank to mark this as global',
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        to='cities_light.country',
                    ),
                ),
                migrations.AlterUniqueTogether(
                    name='categorysubcategory',
                    unique_together={('category', 'subcategory', 'country')},
                ),
            ],
        ),
    ]