from django.db import models
from django.utils.translation import gettext_lazy as _

from pages.models.building import Building


class LightingSpaceType(models.Model):
    """A room or space function a lighting system can serve.

    Replaces the old six-option `RoomType` enum, which was the same short list
    for every building and drove nothing in the calculation. Holding these in a
    table lets each country's own standard supply the list and a reference
    lighting power density, and lets the dropdown be filtered by the building
    type the user already chose.

    `is_common` marks spaces that occur in every kind of building (toilet,
    stairs, parking) so they are not repeated per building category - SNI
    6197:2020 lists several of them three times over with identical values.
    """

    code = models.CharField(max_length=60, unique=True)
    name = models.CharField(max_length=120, verbose_name=_("Space / room"))
    is_common = models.BooleanField(
        default=False,
        help_text="Shown for every building type rather than one category.",
    )
    building_categories = models.JSONField(
        default=list, blank=True,
        help_text="BuildingCategory names this space applies to. Empty when is_common.",
    )
    legacy = models.BooleanField(
        default=False,
        help_text="One of the original six room types. Kept so existing records "
                  "still display, but hidden when adding a new lighting system.",
    )
    sort_order = models.PositiveSmallIntegerField(default=100)

    class Meta:
        ordering = ["-is_common", "sort_order", "name"]
        verbose_name = _("Lighting space type")

    def __str__(self):
        return self.name


class LightingReference(models.Model):
    """A national standard's reference value for a space, or for a whole building.

    Countries differ in what their standard actually publishes, so this carries
    either basis:

      room     - the standard gives a value per room (Indonesia SNI 6197:2020,
                 India ECBC space-function method). `space_type` is set.
      building - the standard gives one limit for the whole building, averaged
                 over its floor area (Vietnam QCVN 09:2017/BXD, Thailand BEC).
                 `building_category` is set instead.

    Cambodia deliberately has no rows: it has no building energy code, so BEAT
    shows no benchmark there rather than inventing one.
    """

    class Basis(models.TextChoices):
        ROOM = "room", _("Per room")
        BUILDING = "building", _("Whole building average")

    country = models.ForeignKey(
        "cities_light.Country", on_delete=models.CASCADE,
        related_name="lighting_references",
    )
    space_type = models.ForeignKey(
        LightingSpaceType, null=True, blank=True, on_delete=models.CASCADE,
        related_name="references",
    )
    building_category = models.CharField(
        max_length=120, null=True, blank=True,
        help_text="Used when basis is 'building'.",
    )
    basis = models.CharField(max_length=20, choices=Basis.choices, default=Basis.ROOM)

    lpd_w_m2 = models.DecimalField(
        max_digits=6, decimal_places=2, null=True, blank=True,
        verbose_name=_("Reference lighting power density (W/m²)"),
    )
    lux = models.PositiveIntegerField(
        null=True, blank=True, verbose_name=_("Required illuminance (lux)"),
    )
    standard = models.CharField(max_length=120)
    tier = models.CharField(
        max_length=40, null=True, blank=True,
        help_text="Stringency tier where the standard has them (ECBC / ECBC+ / Super ECBC).",
    )
    notes = models.CharField(max_length=255, null=True, blank=True)

    class Meta:
        verbose_name = _("Lighting reference value")
        indexes = [models.Index(fields=["country", "basis"])]

    def __str__(self):
        target = self.space_type or self.building_category
        return f"{self.country} · {target} · {self.lpd_w_m2} W/m²"


class RoomType(models.TextChoices):
    """Superseded by LightingSpaceType; kept so historical values still resolve."""

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

    # Stays a CharField rather than becoming a foreign key: ~490 existing
    # records hold the old enum codes, and those codes are preserved in
    # LightingSpaceType (legacy=True) so they still resolve to a label.
    # New entries store a LightingSpaceType.code.
    room_type = models.CharField(max_length=50, verbose_name=_("Room Type"))

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

    total_energy_consumption_kwh_per_year = models.DecimalField(
        max_digits=12,
        decimal_places=3,
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
    def get_room_type_display(self):
        """Human label for the stored room-type code.

        `room_type` dropped its `choices` when the space list moved into
        LightingSpaceType, so Django no longer generates this automatically.
        Resolves against the table, including the six legacy codes that ~490
        existing records still hold, and falls back to the raw code so a value
        from an older import never renders blank.
        """
        if not self.room_type:
            return ""
        space = LightingSpaceType.objects.filter(code=self.room_type).only("name").first()
        return space.name if space else self.room_type
