from django.db import models
from django.utils.translation import gettext_lazy as _

from pages.models.building import Building


class VentilationType(models.TextChoices):
    AHU = "AHU", _("Air Handling Units (AHUs)")
    FCU = "FCU", _("Fan Coil Units (FCUs)")
    CASSETTE_AC = "CASSETTE_AC", _("Ceiling or Wall Mounted Cassette ACs")
    DOAS = "DOAS", _("DOAS")
    FAN = "FAN", _("Ceiling/Exhaust/Wall Fan")
    OTHER = "OTHER", _("Other Ventilation Type")


class VentilationCapacity(models.TextChoices):
    M3H = "M3H", _("m³/hr")
    F3M = "F3M", _("ft³/min")


class VentilationSystem(models.Model):
    building = models.ForeignKey(Building, on_delete=models.CASCADE, related_name="ventilation_systems",
                                 verbose_name=_("Building"))

    ventilation_type = models.CharField(
        max_length=50,
        choices=VentilationType.choices,
        verbose_name=_("Ventilation Type")
    )

    ventilation_capacity = models.CharField(
        max_length=50,
        choices=VentilationCapacity.choices,
        verbose_name=_("Ventilation Capacity")
    )

    baseline_efficiency_w_cmh = models.PositiveIntegerField(
        verbose_name=_("Baseline Ventilation System Efficiency (W/CMH)"))
    operation_hours_per_workday = models.PositiveSmallIntegerField(null=True, blank=True,
                                                                   verbose_name=_("Operation Hours per Workday"))
    workdays_per_week = models.PositiveSmallIntegerField(null=True, blank=True, verbose_name=_("Workdays per Week"))
    workweeks_per_year = models.PositiveSmallIntegerField(null=True, blank=True, verbose_name=_("Workweeks per Year"))
    total_power_input_w = models.PositiveIntegerField(verbose_name=_("Total Ventilation System Power Input (W)"))
    air_flow_rate = models.PositiveIntegerField(verbose_name=_("Air Flow Rate (CMH/CFM)"))
    demand_controlled_ventilation = models.BooleanField(
        verbose_name=_("Installation of Demand Controlled Ventilation (DCV)"), default=False)
    variable_speed_drives = models.BooleanField(verbose_name=_("Installation of Variable Speed Drives (VSDs)"),
                                                default=False)
    number_of_units_installed = models.PositiveIntegerField(
        verbose_name=_("Total Number of Ventilation Type Installed"))
    total_energy_consumption_kwh_per_year = models.PositiveIntegerField(null=True, blank=True, verbose_name=_(
        "Total Energy Consumption of Ventilation System Annually (kWh/year)"))
    energy_efficiency_label = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        choices=[(i, _(str(i))) for i in range(1, 6)],
        verbose_name=_("Energy Efficiency Label")
    )