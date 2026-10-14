from django.db import models
from django.utils.translation import gettext_lazy as _

from pages.models.building import Building


class VentilationType(models.TextChoices):
    AHU = "AHU", _("Air Handling Unit (AHU)")
    FCU = "FCU", _("Fan Coil Unit (FCU)")
    CASSETTE_AC = "CASSETTE_AC", _("Ceiling/Wall Mounted Cassette AC")
    DOAS = "DOAS", _("Dedicated Outdoor Air System (DOAS)")
    FAN = "FAN", _("Ceiling/Exhaust/Wall Fan")


class VentilationCapacity(models.TextChoices):
    M3H = "M3H", _("m³/hr")
    F3M = "F3M", _("ft³/min")


class VentilationSystem(models.Model):
    building = models.ForeignKey(
        Building,
        on_delete=models.CASCADE,
        related_name="ventilation_systems",
        verbose_name=_("Building"),
    )

    # --- link to the cooling system this fan belongs to -------------------
    # Optional, and null for every record entered before this existed, so an
    # unlinked fan is added exactly as it always was.
    #
    # Two fields rather than a generic relation: there are only two kinds of
    # parent, the forms and admin stay readable, and a wrong type cannot be
    # stored. SET_NULL so deleting a cooling record unlinks its fans rather
    # than deleting them with it.
    cooling_parent_ac = models.ForeignKey(
        "pages.CoolingSystemAirConditioner",
        on_delete=models.SET_NULL, null=True, blank=True,
        related_name="indoor_fans",
        verbose_name=_("Part of this air conditioning system"),
    )
    cooling_parent_chiller = models.ForeignKey(
        "pages.CoolingSystemChiller",
        on_delete=models.SET_NULL, null=True, blank=True,
        related_name="indoor_fans",
        verbose_name=_("Served by this chiller"),
    )

    ventilation_type = models.CharField(
        max_length=50,
        choices=VentilationType.choices,
        verbose_name=_("Ventilation Type"),
    )

    ventilation_capacity = models.CharField(
        max_length=50,
        choices=VentilationCapacity.choices,
        null=True,
        blank=True,
        verbose_name=_("Ventilation Capacity"),
    )

    baseline_efficiency_w_cmh = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        verbose_name=_("Baseline Ventilation System Efficiency (W/CMH)")
    )
    operation_hours_per_workday = models.PositiveSmallIntegerField(
        null=True, blank=True, verbose_name=_("Operation Hours per Workday")
    )
    workdays_per_week = models.PositiveSmallIntegerField(
        null=True, blank=True, verbose_name=_("Workdays per Week")
    )
    workweeks_per_year = models.PositiveSmallIntegerField(
        null=True, blank=True, verbose_name=_("Workweeks per Year")
    )
    total_power_input_kw = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name=_("Total Ventilation System Power Input (kW)")
    )
    air_flow_rate = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name=_("Air Flow Rate (CMH/CFM)")
    )
    demand_controlled_ventilation = models.BooleanField(
        verbose_name=_("Installation of Demand Controlled Ventilation (DCV)"),
        default=False,
    )
    variable_speed_drives = models.BooleanField(
        verbose_name=_("Installation of Variable Speed Drives (VSDs)"), default=False
    )
    number_of_units_installed = models.PositiveIntegerField(
        verbose_name=_("Total Number of Ventilation Type Installed")
    )
    total_energy_consumption_kwh_per_year = models.DecimalField(
        max_digits=12,
        decimal_places=3,
        null=True,
        blank=True,
        verbose_name=_(
            "Total Energy Consumption of Ventilation System Annually (kWh/year)"
        ),
    )
    fresh_air_ratio_percent = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        verbose_name=_("Fresh Air Ratio (%)"),
    )
    number_of_stars = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        choices=[(i, _(str(i))) for i in range(1, 6)],
        verbose_name=_("Number of Stars (1–5)"),
    )

    @property
    def cooling_parent(self):
        """The cooling record this fan belongs to, or None."""
        return self.cooling_parent_ac or self.cooling_parent_chiller

    @property
    def fan_energy_already_counted(self) -> bool:
        """True when the parent's figure already includes this fan.

        False for an unlinked fan and for a parent whose boundary is not
        specified, so nothing entered before this existed is reduced.
        """
        from pages.models.building_operation.energy_boundary import (
            fan_is_already_counted)
        return fan_is_already_counted(self.cooling_parent)
