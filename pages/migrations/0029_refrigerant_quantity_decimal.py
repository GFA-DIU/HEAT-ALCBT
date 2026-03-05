from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('pages', '0028_add_ac_capacity_eer_fields'),
    ]

    operations = [
        migrations.AlterField(
            model_name='coolingsystemchiller',
            name='refrigerant_quantity_kg',
            field=models.DecimalField(decimal_places=2, max_digits=8, verbose_name='Refrigerant Quantity (Kg)'),
        ),
        migrations.AlterField(
            model_name='coolingsystemairconditioner',
            name='refrigerant_quantity_kg',
            field=models.DecimalField(decimal_places=2, max_digits=8, verbose_name='Refrigerant Quantity (Kg)'),
        ),
    ]