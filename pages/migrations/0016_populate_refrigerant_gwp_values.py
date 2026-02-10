from django.db import migrations

REFRIGERANT_GWP_DATA = [
    ("R-290", 3),
    ("R-600a", 3),
    ("R-717", 0),
    ("R-744", 1),
    ("R-12", 10900),
    ("R-13", 14400),
    ("R-22", 1810),
    ("R-23", 14800),
    ("R-32", 675),
    ("R-41", 92),
    ("R-125", 3500),
    ("R-134a", 1430),
    ("R-143a", 4470),
    ("R-227EA", 3220),
    ("R-236CB", 1340),
    ("R-236EA", 1370),
    ("R-236FA", 9810),
    ("R-245CA", 693),
    ("R-245FA", 1030),
    ("R-404A", 3922),
    ("R-407A", 1923),
    ("R-407B", 2804),
    ("R-407C", 1624),
    ("R-407D", 1627),
    ("R-407E", 1552),
    ("R-407F", 1825),
    ("R-407G", 1463),
    ("R-410A", 2088),
    ("R-410B", 2229),
    ("R-413A", 2053),
    ("R-417A", 2346),
    ("R-417B", 3027),
    ("R-417C", 1809),
    ("R-419A", 2967),
    ("R-419B", 2384),
    ("R-421A", 2631),
    ("R-421B", 3190),
    ("R-422A", 3143),
    ("R-422B", 2526),
    ("R-422C", 3085),
    ("R-422D", 2729),
    ("R-423A", 2280),
    ("R-424A", 2440),
    ("R-425A", 1505),
    ("R-426A", 1508),
    ("R-427A", 2138),
    ("R-428A", 3607),
    ("R-429A", 13),
    ("R-430A", 94),
    ("R-431A", 36),
    ("R-434A", 3245),
    ("R-435A", 26),
    ("R-437A", 1805),
    ("R-438A", 2264),
    ("R-439A", 1983),
    ("R-440A", 144),
    ("R-442A", 1888),
    ("R-444A", 87),
    ("R-444B", 293),
    ("R-445A", 129),
    ("R-446A", 459),
    ("R-447A", 582),
    ("R-447B", 739),
    ("R-448A", 1386),
    ("R-449A", 1396),
    ("R-449B", 1411),
    ("R-449C", 1250),
    ("R-450A", 601),
    ("R-451A", 146),
    ("R-451B", 160),
    ("R-452A", 2139),
    ("R-452B", 697),
    ("R-452C", 2219),
    ("R-453A", 1765),
    ("R-454A", 236),
    ("R-454B", 465),
    ("R-454C", 145),
    ("R-455A", 145),
    ("R-456A", 684),
    ("R-457A", 136),
    ("R-458A", 1650),
    ("R-500", 8077),
    ("R-502", 4785),
    ("R-503", 3600),
    ("R-507A", 3985),
    ("R-508A", 3214),
    ("R-508B", 3396),
    ("R-512A", 189),
    ("R-513A", 629),
    ("R-513B", 593),
    ("R-515A", 386),
]


def populate_gwp_values(apps, schema_editor):
    RefrigerantGWP = apps.get_model("pages", "RefrigerantGWP")
    RefrigerantGWP.objects.bulk_create(
        [RefrigerantGWP(refrigerant_code=code, gwp_value=gwp) for code, gwp in REFRIGERANT_GWP_DATA],
        ignore_conflicts=True,
    )


def remove_gwp_values(apps, schema_editor):
    RefrigerantGWP = apps.get_model("pages", "RefrigerantGWP")
    codes = [code for code, _ in REFRIGERANT_GWP_DATA]
    RefrigerantGWP.objects.filter(refrigerant_code__in=codes).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("pages", "0015_add_refrigerant_gwp_model"),
    ]

    operations = [
        migrations.RunPython(populate_gwp_values, remove_gwp_values),
    ]
