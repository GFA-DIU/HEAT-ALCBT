from django.db import models
from django.utils.translation import gettext_lazy as _

from pages.models.building import Building
from pages.models.building_operation.chilling import RefrigerantType


class CoolingSystemAirConditioner(models.Model):
    building = models.ForeignKey(
        Building,
        on_delete=models.CASCADE,
        related_name="air_conditioners",
        verbose_name=_("Building"),
    )
    ac_type = models.CharField(
        max_length=50,
        choices=[
            ("vrv", _("VRV/VRF (Variable Refrigerant Volume/Flow)")),
            ("split", _("Split Air Conditioners")),
        ],
        verbose_name=_("Air Conditioners Type"),
    )
    year_of_installation = models.PositiveIntegerField(
        verbose_name=_("Year of Installation")
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
    refrigerant_type = models.CharField(
        max_length=50,
        choices=RefrigerantType.choices,
        verbose_name=_("Type of Refrigerants"),
    )
    refrigerant_quantity_kg = models.PositiveIntegerField(
        verbose_name=_("Refrigerant Quantity (Kg)")
    )
    total_cooling_load_rt = models.PositiveIntegerField(
        verbose_name=_("Total Cooling Load for Split/VRV (RT)")
    )
    baseline_efficiency_kw_per_rt = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name=_("Baseline Split Unit/VRV System Efficiency (kW/RT)"),
    )
    baseline_refrigerant_emission_factor = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name=_("Baseline Refrigerant Emission Factor (GWP)"),
    )
    baseline_leakage_factor_percent = models.PositiveIntegerField(
        default=2, verbose_name=_("Baseline Leakage Factor (%)")
    )
    total_energy_consumption_kwh_per_year = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name=_(
            "Total Energy Consumption of Cooling System Annually (kWh/year)"
        ),
    )
    number_of_units = models.PositiveIntegerField(
        verbose_name=_("Total Number of Split/VRV Units")
    )
    total_system_power_kw = models.PositiveIntegerField(
        null=True, blank=True, verbose_name=_("Total Split Unit/VRV System Power (kW)")
    )
    cop = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True, verbose_name=_("COP")
    )
    iseer_rating = models.DecimalField(
        max_digits=4,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name=_("ISEER Rating"),
    )
    energy_efficiency_label = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        choices=[(i, _(str(i))) for i in range(1, 6)],
        verbose_name=_("Energy Efficiency Label"),
    )
