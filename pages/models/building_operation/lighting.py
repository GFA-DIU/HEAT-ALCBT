from django.db import models
from django.utils.translation import gettext_lazy as _

from pages.models.building import Building


class RoomType(models.TextChoices):
    OFFICE_CONFERENCE = "OFFICE_CONFERENCE", _("Office: Conference Room")
    HOSPITAL_PATIENT = "HOSPITAL_PATIENT", _("Hospital: Patient Room")
    RESIDENTIAL_KITCHEN = "RESIDENTIAL_KITCHEN", _("Residential: Kitchen")
    RESIDENTIAL_DINING = "RESIDENTIAL_DINING", _("Residential: Dining Room")
    COMMERCIAL_GENERAL = "COMMERCIAL_GENERAL", _("Commercial: General Office/Retail")
    COMMERCIAL_MALL = "COMMERCIAL_MALL", _("Commercial: Mall / Department Store")


class LightingBulbType(models.TextChoices):
    LED_PANEL = "LED_PANEL", _("LED Panel")
    LED_TUBE = "LED_TUBE", _("LED Tube")
    LED_DOWNLIGHT = "LED_DOWNLIGHT", _("LED Downlight")
    LED_BULB = "LED_BULB", _("LED Bulb")
    LED_STRIP = "LED_STRIP", _("LED Strip")
    FLUORESCENT_T5 = "FLUORESCENT_T5", _("Fluorescent T5")
    FLUORESCENT_T8 = "FLUORESCENT_T8", _("Fluorescent T8")
    FLUORESCENT_T12 = "FLUORESCENT_T12", _("Fluorescent T12")
    CFL = "CFL", _("CFL")
    INCANDESCENT = "INCANDESCENT", _("Incandescent")
    HALOGEN = "HALOGEN", _("Halogen")
    METAL_HALIDE = "METAL_HALIDE", _("Metal Halide")
    HIGH_PRESSURE_SODIUM = "HIGH_PRESSURE_SODIUM", _("High-Pressure Sodium")


class EnergyEfficiencyLabelType(models.TextChoices):
    BEE = "BEE", _("BEE Star Rating")
    EGAT = "EGAT", _("EGAT Label No")
    ESDM = "ESDM", _("ESDM decree")
    OTHERS = "OTHERS", _("Others")


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
        verbose_name=_("Type of Lighting System"),
    )

    number_of_bulbs = models.PositiveIntegerField(
        verbose_name=_("Total Number of Fixtures Installed")
    )

    tubes_per_fixture = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        verbose_name=_("Number of Tubes per Fixture"),
    )

    light_bulb_power_rating_w = models.PositiveIntegerField(
        verbose_name=_("Wattage per Fixture/Lamp (W)")
    )

    total_lighting_power_kw = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        null=True,
        blank=True,
        verbose_name=_("Total Lighting Power (kW)"),
    )

    baseline_lighting_power_density = models.DecimalField(
        max_digits=10,
        decimal_places=6,
        null=True,
        blank=True,
        verbose_name=_("Baseline Lighting Power Density (kW/m²)"),
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

    energy_efficiency_label = models.CharField(
        max_length=10,
        choices=EnergyEfficiencyLabelType.choices,
        null=True,
        blank=True,
        verbose_name=_("Energy Efficiency Label"),
    )

    number_of_stars = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        choices=[(i, _(str(i))) for i in range(1, 6)],
        verbose_name=_("Number of Stars (1–5)"),
    )