from django.db import models
from django.utils.translation import gettext_lazy as _
from django.core.validators import MinValueValidator, MaxValueValidator

from pages.models.building import Building


class HotWaterSystemType(models.TextChoices):
    HEAT_PUMP = "heat-pump", _("Heat Pump Water Heater")
    BOILER = "boiler", _("Boiler")
    SOLAR = "solar", _("Solar Water Heaters")


class FuelType(models.TextChoices):
    ELECTRICITY = "electricity", _("Electricity")
    LIGHT_FUEL_OIL = "light-fuel-oil", _("Light Fuel Oil")
    HEAVY_FUEL_OIL = "heavy-fuel-oil", _("Heavy Fuel Oil")
    LPG = "lpg", _("Liquified Petroleum Gas (LPG)")
    NATURAL_GAS = "natural-gas", _("Natural Gas")
    COAL = "coal", _("Coal")
    LIGNITE = "lignite", _("Lignite")
    DIESEL = "diesel", _("Diesel")
    KEROSENE = "kerosene", _("Kerosene")
    FIRE_WOOD_LOG = "fire-wood-log", _("Fire Wood (Log Wood)")
    FIRE_WOOD_CHIPS = "fire-wood-chips", _("Fire Wood (Wood Chips)")
    FIRE_WOOD_PELLETS = "fire-wood-pellets", _("Fire Wood (Wood Pellets)")
    CHAR_COAL = "char-coal", _("Char Coal")
    IGNITE = "ignite", _("Ignite")
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
        verbose_name=_("Fuel Type")
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

    fuel_consumption = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        verbose_name=_("Fuel Consumption (Liters/m³)"),
    )

    power_input = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        verbose_name=_("Hot Water System Power Input (kW)"),
        db_column="power_input_kw",
    )

    baseline_efficiency = models.DecimalField(
        max_digits=10,
        decimal_places=3,
        validators=[MinValueValidator(0)],
        verbose_name=_("Baseline Hot Water System Efficiency (COP)"),
        db_column="baseline_efficiency_cop",
    )

    equipment_efficiency_level = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        verbose_name=_("Baseline Hot Water System Equipment Efficiency Level (%)"),
        db_column="baseline_equipment_efficiency_percentage",
    )

    heat_recovery_system = models.BooleanField(
        verbose_name=_("Installation of Heat Recovery Systems"),
        default=False,
        db_column="heat_recovery_installed",
    )

    number_of_equipment = models.PositiveIntegerField(
        validators=[MinValueValidator(1)],
        verbose_name=_("Number of Hot Water Equipment Installed"),
        db_column="number_of_equipments",
    )

    energy_efficiency_label = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        verbose_name=_("Energy Efficiency Star Rating (1-5)"),
    )

    class Meta:
        verbose_name = _("Hot Water System")
        verbose_name_plural = _("Hot Water Systems")
        ordering = ["-id"]

    def __str__(self):
        return f"{self.get_type_of_hot_water_system_display()} - {self.building.name}"
