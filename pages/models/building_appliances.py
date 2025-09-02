from django.db import models
from .building import (
    Building,
    CategorySubcategory
)
from cities_light.models import Country


class SystemType(models.Model):
    """
    Represents a system or a subtype in a hierarchical parent-child structure.
    If parent is null, this is a top-level system (e.g., Chiller, AC).
    If parent is set, this is a subtype of that parent (e.g., Air Cooler under Chiller).
    """
    name = models.CharField(max_length=100, unique=False)
    parent = models.ForeignKey(
        "self",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="subtypes"
    )
    description = models.TextField(null=True, blank=True)

    class Meta:
        unique_together = ("parent", "name")

    def __str__(self):
        if self.parent:
            return f"{self.parent.name} → {self.name}"
        return self.name


class BuildingSystem(models.Model):
    building = models.ForeignKey(Building, on_delete=models.CASCADE, related_name="systems")
    system_type = models.ForeignKey(SystemType, on_delete=models.CASCADE, related_name="system_type_building_system")
    capacity = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    capacity_unit = models.CharField(max_length=20, null=True, blank=True)
    contribution_percent = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True
    )

    class Meta:
        unique_together = ("building", "system_type")  # ensures no duplicate subtype per building


class Benchmark(models.Model):
    building_type = models.ForeignKey(CategorySubcategory, on_delete=models.CASCADE)
    country = models.ForeignKey(Country, on_delete=models.CASCADE, null=True, blank=True)  # blank = universal
    system_type = models.ForeignKey(SystemType, on_delete=models.CASCADE, related_name="system_type_bench_mark")
    eui = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)  # kWh/m²/year
    lpd = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)  # W/m²
    efficiency = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)  # %

    class Meta:
        unique_together = ("building_type", "country", "system_type")
