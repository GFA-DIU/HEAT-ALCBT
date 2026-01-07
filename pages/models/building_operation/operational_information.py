from django.db import models
from django.utils.translation import gettext_lazy as _

from pages.models.building import Building


class BuildingOperation(models.Model):
    building = models.OneToOneField(
        Building,
        on_delete=models.CASCADE,
        related_name="operation",
        verbose_name=_("Building"),
    )
    number_of_residents = models.PositiveIntegerField(
        verbose_name=_("Number of Residents")
    )
    operation_hours_per_workday = models.PositiveSmallIntegerField(
        choices=[(i, _(str(i))) for i in range(1, 25)],
        verbose_name=_("Operation Hours per Workday"),
    )
    workdays_per_week = models.PositiveSmallIntegerField(
        choices=[(i, _(str(i))) for i in range(1, 8)],
        verbose_name=_("Workdays per Week"),
    )
    workweeks_per_year = models.PositiveSmallIntegerField(
        choices=[(i, _(str(i))) for i in range(1, 53)],
        verbose_name=_("Workweeks per Year"),
    )
    renewable_energy_percent = models.PositiveIntegerField(
        verbose_name=_("Renewable Energy (%)"),
        help_text=_(
            "Percentage of the annual energy consumption of the building produced on site from renewable sources"
        ),
    )
    energy_monitoring_control_systems = models.BooleanField(
        verbose_name=_("Energy Monitoring and Control Systems"), default=False
    )
