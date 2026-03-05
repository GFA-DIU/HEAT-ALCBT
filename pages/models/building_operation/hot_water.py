from django.db import models
from django.utils.translation import gettext_lazy as _
from django.core.validators import MinValueValidator, MaxValueValidator

from pages.models.building import Building


class HotWaterSystemType(models.TextChoices):
    HEAT_PUMP = "heat-pump", _("Heat Pump Water Heater")
    BOILER = "boiler", _("Boiler")
    SOLAR = "solar", _("Water Heaters")


class FuelType(models.TextChoices):
    ELECTRICITY = "electricity", _("Electricity")
    NATURAL_GAS = "natural-gas", _("Natural Gas")
    LPG = "lpg", _("LPG")
    DIESEL = "diesel", _("Diesel")
    KEROSENE = "kerosene", _("Kerosene")
    COAL = "coal", _("Coal")
    SOLAR = "solar", _("Solar")
    LIGHT_FUEL_OIL = "light-fuel-oil", _("Light Fuel Oil")
    HEAVY_FUEL_OIL = "heavy-fuel-oil", _("Heavy Fuel Oil")
    LIGNITE = "lignite", _("Lignite")
    FIRE_WOOD_LOG = "fire-wood-log", _("Fire Wood (Log Wood)")
    FIRE_WOOD_CHIPS = "fire-wood-chips", _("Fire Wood (Wood Chips)")
    FIRE_WOOD_PELLETS = "fire-wood-pellets", _("Fire Wood (Wood Pellets)")
    CHAR_COAL = "char-coal", _("Charcoal")
    IGNITE = "ignite", _("Ignite")
    NONE = "none", _("None")
    OTHER = "other", _("Other")


class EnergyEfficiencyLabelType(models.TextChoices):
    BEE = "bee", _("BEE Star Rating")
    EGAT = "egat", _("EGAT")


class HotWaterSystem(models.Model):
    """
    Model to store Hot Water System data for a building.
    Each building can have multiple hot water systems.
    """
    building = models.ForeignKey(
        Building,
        on_delete=models.CASCADE,
        related_name="hot_water_systems",
        verbose_name=_("Building"),
    )

    type_of_hot_water_system = models.CharField(
        max_length=50,
        choices=HotWaterSystemType.choices,
        verbose_name=_("Type of Hot Water System"),
        db_column="system_type",
    )

    fuel_type = models.CharField(
        max_length=50,
        choices=FuelType.choices,
        verbose_name=_("Fuel Type"),
    )

    number_of_equipment = models.PositiveIntegerField(
        validators=[MinValueValidator(1)],
        verbose_name=_("Number of Hot Water Equipment Installed"),
        db_column="number_of_equipments",
    )

    operating_hours_per_day = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(0), MaxValueValidator(24)],
        verbose_name=_("Operating Hours per Day"),
        db_column="operation_hours_per_workday",
    )

    operating_days_per_week = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(0), MaxValueValidator(7)],
        verbose_name=_("Operating Days per Week"),
        db_column="workdays_per_week",
    )

    operating_weeks_per_year = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(0), MaxValueValidator(52)],
        verbose_name=_("Operating Weeks per Year"),
        db_column="workweeks_per_year",
    )

    baseline_efficiency = models.DecimalField(
        max_digits=10,
        decimal_places=3,
        validators=[MinValueValidator(0)],
        verbose_name=_("Baseline Hot Water System Efficiency"),
        db_column="baseline_efficiency_cop",
    )

    heat_recovery_system = models.BooleanField(
        verbose_name=_("Installation of Heat Recovery Systems"),
        default=False,
        db_column="heat_recovery_installed",
    )

    equipment_efficiency_level = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        verbose_name=_("Baseline Hot Water System Equipment Efficiency Level (%)"),
        db_column="baseline_equipment_efficiency_percentage",
    )

    power_input = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
        verbose_name=_("Hot Water System Power Input (kW)"),
        db_column="power_input_kw",
    )

    total_energy_consumption_kwh_per_year = models.DecimalField(
        max_digits=12,
        decimal_places=3,
        null=True,
        blank=True,
        verbose_name=_("Total Energy Consumption Annually (kWh/year)"),
    )

    total_fuel_consumption = models.DecimalField(
        max_digits=15,
        decimal_places=3,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
        verbose_name=_("Total Fuel Consumption (Boiler)"),
    )

    fuel_consumption_unit = models.CharField(
        max_length=20,
        null=True,
        blank=True,
        verbose_name=_("Fuel Consumption Unit"),
    )

    class Meta:
        verbose_name = _("Hot Water System")
        verbose_name_plural = _("Hot Water Systems")
        ordering = ["-id"]

    def __str__(self):
        return f"{self.get_type_of_hot_water_system_display()} - {self.building.name}"