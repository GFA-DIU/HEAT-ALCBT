from django.db import models
from django.utils.translation import gettext_lazy as _

from pages.models.building import Building

class HotWaterSystemType(models.TextChoices):
    HEAT_PUMP = "HEAT_PUMP", _("Heat Pump Water Heater")
    BOILER = "BOILER", _("Boiler")
    SOLAR = "SOLAR", _("Solar Water Heaters")


class FuelType(models.TextChoices):
    ELECTRICITY = "ELECTRICITY", _("Electricity")
    LIGHT_FUEL_OIL = "LIGHT_FUEL_OIL", _("Light Fuel Oil")
    HEAVY_FUEL_OIL = "HEAVY_FUEL_OIL", _("Heavy Fuel Oil")
    LPG = "LPG", _("Liquefied Petroleum Gas (LPG)")
    NATURAL_GAS = "NATURAL_GAS", _("Natural Gas")
    COAL = "COAL", _("Coal")
    LIGNITE = "LIGNITE", _("Lignite")
    DIESEL = "DIESEL", _("Diesel")
    KEROSENE = "KEROSENE", _("Kerosene")
    FIRE_WOOD_LOG = "FIRE_WOOD_LOG", _("Fire Wood (Log Wood)")
    FIRE_WOOD_CHIPS = "FIRE_WOOD_CHIPS", _("Fire Wood (Wood Chips)")
    FIRE_WOOD_PELLETS = "FIRE_WOOD_PELLETS", _("Fire Wood (Wood Pellets)")
    CHAR_COAL = "CHAR_COAL", _("Char Coal")
    OTHER = "OTHER", _("Other")


class HotWaterSystem(models.Model):
    building = models.ForeignKey(
        Building,
        on_delete=models.CASCADE,
        related_name="hot_water_systems",
        verbose_name=_("Building")
    )

    system_type = models.CharField(
        max_length=50,
        choices=HotWaterSystemType.choices,
        verbose_name=_("Type of Hot Water System")
    )

    operation_hours_per_workday = models.PositiveSmallIntegerField(
        verbose_name=_("Operation Hours for Hot Water per Workday")
    )
    workdays_per_week = models.PositiveSmallIntegerField(verbose_name=_("Workdays per Week"))
    workweeks_per_year = models.PositiveSmallIntegerField(verbose_name=_("Workweeks per Year"))

    fuel_type = models.CharField(
        max_length=50,
        choices=FuelType.choices,
        verbose_name=_("Fuel Type")
    )

    fuel_consumption = models.PositiveIntegerField(verbose_name=_("Fuel Consumption (Liters/m³)"))

    power_input_kw = models.PositiveIntegerField(verbose_name=_("Hot Water System Power Input (kW)"))
    baseline_efficiency_cop = models.PositiveIntegerField(verbose_name=_("Baseline Hot Water System Efficiency (COP)"))
    baseline_equipment_efficiency_percentage = models.PositiveIntegerField(
        verbose_name=_("Baseline Hot Water System Equipment Efficiency Level (%)"))

    heat_recovery_installed = models.BooleanField(
        verbose_name=_("Installation of Heat Recovery Systems"),
        default=False
    )

    number_of_equipments = models.PositiveIntegerField(verbose_name=_("Number of Hot Water Equipment Installed"))

    energy_efficiency_label = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        choices=[(i, _(str(i))) for i in range(1, 6)],
        verbose_name=_("Energy Efficiency Label")
    )

    class Meta:
        verbose_name = _("Hot Water System")
        verbose_name_plural = _("Hot Water Systems")