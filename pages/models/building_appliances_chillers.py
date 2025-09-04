from django.db.models.signals import post_migrate
from django.dispatch import receiver
from django.apps import apps
import logging

from django.db import models
from .building import (
    Building,
    CategorySubcategory
)
from cities_light.models import Country


class Refrigerant(models.Model):
    name = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.name


class Chiller(models.Model):
    CHILLER_TYPES = [
        ('water', 'Water Cooled Chiller'),
        ('air', 'Air Cooled Chiller'),
    ]

    YES_NO = [
        ('yes', 'Yes'),
        ('no', 'No'),
    ]

    # Core relationship
    building = models.ForeignKey('Building', on_delete=models.CASCADE, related_name='chillers')

    # Mandatory fields
    chiller_type = models.CharField(max_length=20, choices=CHILLER_TYPES)
    year_of_installation = models.PositiveIntegerField()
    operation_hours_per_workday = models.PositiveIntegerField(default=8)
    workdays_per_week = models.PositiveIntegerField(default=6)
    workweeks_per_year = models.PositiveIntegerField(default=50)

    # Refrigerant info
    refrigerant_type = models.ForeignKey('Refrigerant', on_delete=models.PROTECT)
    refrigerant_quantity_kg = models.FloatField(help_text="Quantity in Kg")

    # Cooling / performance
    total_cooling_load_rt = models.FloatField(help_text="Refrigeration Tonnage (RT)")
    baseline_cooling_efficiency_kw_rt = models.FloatField(default=1.5, help_text="kW/RT")

    vsd_installed = models.CharField(max_length=3, choices=YES_NO)
    heat_recovery_installed = models.CharField(max_length=3, choices=YES_NO)

    # Optional / calculated fields
    baseline_refrigerant_emission_factor = models.FloatField(null=True, blank=True, help_text="GWP")
    baseline_leakage_factor = models.FloatField(null=True, blank=True, help_text="% per year")
    annual_energy_consumption_kwh = models.FloatField(null=True, blank=True)

    number_of_chillers = models.PositiveIntegerField(null=True, blank=True)
    water_cooled_load_factor_percent = models.FloatField(null=True, blank=True, help_text="Optimal ~70–75%")
    total_system_kw = models.FloatField(null=True, blank=True)
    cop = models.FloatField(null=True, blank=True, help_text="Coefficient of Performance")
    iplv = models.FloatField(null=True, blank=True, help_text="Integrated Part Load Value")
    efficiency_label = models.PositiveIntegerField(null=True, blank=True, help_text="Star rating (1–5)")

    class Meta:
        verbose_name = "Chiller"
        verbose_name_plural = "Chillers"
        constraints = [
            models.UniqueConstraint(fields=["building", "chiller_type"], name="unique_building_chiller_type"),
            models.UniqueConstraint(fields=["building", "refrigerant_type"], name="unique_building_refrigerant_type"),
        ]

    def __str__(self):
        return f"{self.building} - {self.get_chiller_type_display()} ({self.refrigerant_type})"


@receiver(post_migrate)
def preload_default_data(sender, **kwargs):
    if sender.name != 'pages':
        return

    # Preload refrigerants
    refrigerants = [
        'R-290 (Propane)', 'R-600a (Isobutane)', 'R-717 (Ammonia)', 'R-744 (CO2)', 'R-12', 'R-13', 'R-22', 'R-23',
        'R-32', 'R-41', 'R-125', 'R-134a', 'R-143a', 'R-227EA', 'R-236CB', 'R-236EA', 'R-236FA', 'R-245CA', 'R-245FA',
        'R-404A', 'R-407A', 'R-407B', 'R-407C', 'R-407D', 'R-407E', 'R-407F', 'R-407G', 'R-410A', 'R-410B', 'R-413A',
        'R-417A', 'R-417B', 'R-417C', 'R-419A', 'R-419B', 'R-421A', 'R-421B', 'R-422A', 'R-422B', 'R-422C', 'R-422D',
        'R-423A', 'R-424A', 'R-425A', 'R-426A', 'R-427A', 'R-428A', 'R-429A', 'R-430A', 'R-431A', 'R-434A', 'R-435A',
        'R-437A', 'R-438A', 'R-439A', 'R-440A', 'R-442A', 'R-444A', 'R-444B', 'R-445A', 'R-446A', 'R-447A', 'R-447B',
        'R-448A', 'R-449A', 'R-449B', 'R-449C', 'R-450A', 'R-451A', 'R-451B', 'R-452A', 'R-452B', 'R-452C', 'R-453A',
        'R-454A', 'R-454B', 'R-454C', 'R-455A', 'R-456A', 'R-457A', 'R-458A', 'R-500', 'R-502', 'R-503', 'R-507A',
        'R-508A', 'R-508B', 'R-512A', 'R-513A', 'R-513B', 'R-515A'
    ]

    try:
        Refrigerant = apps.get_model('pages', 'Refrigerant')
        for ref in refrigerants:
            obj, created = Refrigerant.objects.get_or_create(name=ref)
            if created:
                print(f"Preloaded refrigerant: {ref}")
    except Exception as e:
        print(f"Error preloading refrigerants: {e}")


class ChillerBenchmark(models.Model):
    CHILLER_TYPES = [
        ('water', 'Water Cooled Chiller'),
        ('air', 'Air Cooled Chiller'),
    ]

    country = models.ForeignKey(Country, on_delete=models.CASCADE, null=True, blank=True,
                                related_name='chiller_benchmarks')  # blank = universal
    building_type = models.ForeignKey(CategorySubcategory, on_delete=models.CASCADE)

    chiller_type = models.CharField(max_length=20, choices=CHILLER_TYPES)
    refrigerant_type = models.ForeignKey(Refrigerant, on_delete=models.CASCADE)

    # Benchmark fields
    benchmark_efficiency_kw_rt = models.FloatField(help_text="Benchmark efficiency (kW/RT)")
    benchmark_cop = models.FloatField(help_text="Coefficient of Performance")
    benchmark_iplv = models.FloatField(help_text="Integrated Part Load Value")
    benchmark_emission_factor = models.FloatField(help_text="GWP")
    benchmark_leakage_factor = models.FloatField(help_text="% per year")

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["country", "building_type", "chiller_type", "refrigerant_type"],
                name="unique_country_building_type_chiller_refrigerant_benchmark"
            )
        ]
        verbose_name = "Chiller Benchmark"
        verbose_name_plural = "Chiller Benchmarks"

    def __str__(self):
        return f"{self.country.name or ''} - {self.building_type.category.name} - {self.building_type.subcategory.name} - {self.get_chiller_type_display()} - {self.refrigerant_type.name}"
