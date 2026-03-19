from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    """
    Adds is_template and from_template fields to Assembly.
    Uses IF NOT EXISTS in the SQL so it is safe to run against a production
    database where these columns may already exist, while still creating them
    correctly on a fresh database.
    """

    dependencies = [
        ('pages', '0030_energy_consumption_decimal'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunSQL(
                    sql="""
                        ALTER TABLE pages_assembly
                        ADD COLUMN IF NOT EXISTS is_template boolean NOT NULL DEFAULT false;
                    """,
                    reverse_sql="""
                        ALTER TABLE pages_assembly DROP COLUMN IF EXISTS is_template;
                    """,
                ),
                migrations.RunSQL(
                    sql="""
                        ALTER TABLE pages_assembly
                        ADD COLUMN IF NOT EXISTS from_template_id uuid
                            REFERENCES pages_assembly(id)
                            ON DELETE SET NULL
                            DEFERRABLE INITIALLY DEFERRED;
                    """,
                    reverse_sql="""
                        ALTER TABLE pages_assembly DROP COLUMN IF EXISTS from_template_id;
                    """,
                ),
            ],
            state_operations=[
                migrations.AddField(
                    model_name='assembly',
                    name='is_template',
                    field=models.BooleanField(default=False, help_text='Whether this assembly can be reused as a template'),
                ),
                migrations.AddField(
                    model_name='assembly',
                    name='from_template',
                    field=models.ForeignKey(
                        blank=True,
                        help_text='Original template this was created from',
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name='derived_assemblies',
                        to='pages.assembly',
                    ),
                ),
            ],
        ),
    ]
