from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    """
    Records is_template, public, draft and from_template fields that already
    exist on the Assembly table in production. Uses SeparateDatabaseAndState so
    no DDL is executed against an existing database, but the test runner (which
    builds from scratch) will create the columns correctly.
    """

    dependencies = [
        ('pages', '0030_energy_consumption_decimal'),
    ]

    operations = [
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
    ]