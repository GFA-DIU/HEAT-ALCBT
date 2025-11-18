from django.db import models
from django.utils.translation import gettext_lazy as _

from pages.models.building import Building


class RoomType(models.TextChoices):
    OFFICE_CONFERENCE = "OFFICE_CONFERENCE", _("Office: Conference Room")
    HOSPITAL_PATIENT = "HOSPITAL_PATIENT", _("Hospital: Patient Room")
    RESIDENTIAL_KITCHEN = "RESIDENTIAL_KITCHEN", _("Residential: Kitchen")
    RESIDENTIAL_DINING = "RESIDENTIAL_DINING", _("Residential: Dining")


class LightingBulbType(models.TextChoices):
    CFL = "CFL", _("CFL (Compact Fluorescent Lamp) Lights")
    LED = "LED", _("LED (Light Emitting Diode) Lights")
    T5_T8 = "T5_T8", _("T5 and T8 Fluorescent Tube Lights")
    OTHER = "OTHER", _("Other Lighting Type")


class LightingSystem(models.Model):
    building = models.ForeignKey(
        Building,
        on_delete=models.CASCADE,
        related_name="lighting_systems",
        verbose_name=_("Building"),
    )

    room_type = models.CharField(
        max_length=50, choices=RoomType.choices, verbose_name=_("Room Type")
    )

    area_of_room = models.PositiveIntegerField(verbose_name=_("Area of Room (m²)"))

    lighting_bulb_type = models.CharField(
        max_length=50,
        choices=LightingBulbType.choices,
        verbose_name=_("Lighting Bulb Type"),
    )

    number_of_bulbs = models.PositiveIntegerField(
        verbose_name=_("Number of Lighting Bulbs")
    )
    operation_hours_per_workday = models.PositiveSmallIntegerField(
        verbose_name=_("Operation Hours per Workday")
    )
    workdays_per_week = models.PositiveSmallIntegerField(
        verbose_name=_("Workdays per Week")
    )
    workweeks_per_year = models.PositiveSmallIntegerField(
        verbose_name=_("Workweeks per Year")
    )
    light_bulb_power_rating_w = models.PositiveIntegerField(
        verbose_name=_("Light Bulb Power Rating (W)")
    )
    baseline_lighting_power_density = models.PositiveIntegerField(
        null=True, blank=True, verbose_name=_("Baseline Lighting Power Density (W/m²)")
    )
    sensors_installed = models.BooleanField(
        verbose_name=_("Installation of Sensors"), default=False
    )
    total_energy_consumption_kwh_per_year = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name=_(
            "Total Energy Consumption of Lighting System Annually (kWh/year)"
        ),
    )
    energy_efficiency_label = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        choices=[(i, _(str(i))) for i in range(1, 6)],
        verbose_name=_("Energy Efficiency Label"),
    )
