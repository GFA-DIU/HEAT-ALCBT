from django.db import models
from django.utils.translation import gettext as _
from django.core.validators import MinValueValidator, MaxValueValidator

from pages.views.building.impact_calculation import calculate_impact_operational

from .assembly import Assembly
from .base import BaseGeoModel, BaseModel
from .product import BaseProduct
from .epd import EPD, Unit


class ClimateZone(models.TextChoices):
    HOT_DRY = "hot-dry", "hot-dry"
    WARM_HUMID = "warm-humid", "warm-humid"
    COMPOSITE = "composite", "composite"
    TEMPERATE = "temperate", "temperate"
    COLD = "cold", "cold"
    TROPICAL_WET = "tropical-wet", "tropical wet"


class HeatingType(models.TextChoices):
    ROOM_HEATER = "room-heater", "Room Heaters"
    REVERSE_CYCLE_AC = "reverse_cycle_ac", "Reverse Cycle Air Conditioners (Heat Pumps)"
    SPLIT_AC = "split-ac", "Split AC with Heating Mode"
    PACKAGED_AC = "packaged-ac", "Packaged Air Conditioners with Electric Heating Coils"
    BOILER = "boiler", "Boiler"


class CoolingType(models.TextChoices):
    WINDOW_AC = "window-ac", "Window Air Conditioners"
    SPLIT_AC = "split-ac", "Split Air Conditioners"
    VRF_SYSTEM = "vrf-system", "Variable Refrigerant Flow (VRF) Systems"
    PACKAGED_AC = "packaged-ac", "Packaged Air Conditioners"
    CHILLER_SYSTEM = "chiller-system", "Chiller Systems"


class VentilationType(models.TextChoices):
    AHU = "ahu", "Air Handling Units (AHUs)"
    FCU = "fcu", "Fan Coil Units (FCUs)"
    CASSETTE_AC = "cassette-ac", "Ceiling or Wall-Mounted Cassette Acs"
    DOAS = "doas", "DOAS"


class LightingType(models.TextChoices):
    LED = "led", "LED (Light Emitting Diode) Lights"
    CFL = "cfl", "CFL (Compact Fluorescent Lamp) Lights"
    FLUORESCENT_TUBE = "fluorescent-tube", "T5 and T8 Fluorescent Tube Lights"


class BuildingSubcategory(models.Model):
    name = models.CharField(_("Name"), max_length=255, unique=True)

    def __str__(self):
        return f"{self.name}"

    class Meta:
        verbose_name = "Building subcategory"
        verbose_name_plural = "Building subcategories"


class BuildingCategory(models.Model):
    name = models.CharField(_("Name"), max_length=255, unique=True)
    subcategories = models.ManyToManyField(
        BuildingSubcategory,
        through="CategorySubcategory",
        blank=True,
        related_name="categories",
    )

    class Meta:
        verbose_name = "Building category"
        verbose_name_plural = "Building categories"


class CategorySubcategory(models.Model):
    category = models.ForeignKey(BuildingCategory, on_delete=models.CASCADE)
    subcategory = models.ForeignKey(BuildingSubcategory, on_delete=models.CASCADE)

    class Meta:
        unique_together = ("category", "subcategory")

    def __str__(self):
        return f"{self.category.name} - {self.subcategory.name}"


class BuildingOperationalInfo(models.Model):
    ### Operational Emissions
    operational_components = models.ManyToManyField(
        EPD,
        blank=True,
        related_name="buildings",
        through="OperationalProduct",
    )
    simulated_operational_components = models.ManyToManyField(
        EPD,
        blank=True,
        related_name="buildingsimulations",
        through="SimulatedOperationalProduct",
    )
    ### Building Operation
    num_residents = models.IntegerField(
        _("Approx. number of residents"),
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
    )
    hours_per_workday = models.IntegerField(
        _("Operation hours per workday"),
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(24)],
    )
    workdays_per_week = models.IntegerField(
        _("Operation days per week"),
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(7)],
    )
    weeks_per_year = models.IntegerField(
        _("Operation weeks per year"),
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(52)],
    )
    heating_temp = models.DecimalField(
        _("Typical Heating Temperature"),
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0), MaxValueValidator(120)],
        null=True,
        blank=True,
    )
    heating_temp_unit = models.CharField(
        _("Heating Temperature Unit"),
        max_length=20,
        choices=[c for c in Unit.choices if c[0] in (Unit.CELSIUS, Unit.FAHRENHEIT)],
        null=True,
        blank=True,
    )
    cooling_temp = models.DecimalField(
        _("Typical Cooling Temperature (Celsius)"),
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0), MaxValueValidator(120)],
        null=True,
        blank=True,
    )
    cooling_temp_unit = models.CharField(
        _("Cooling Temperature Unit"),
        max_length=20,
        choices=[c for c in Unit.choices if c[0] in (Unit.CELSIUS, Unit.FAHRENHEIT)],
        null=True,
        blank=True,
    )
    ### Building Services
    heating_type = models.CharField(
        _("Heating Type"),
        max_length=50,
        choices=HeatingType.choices,
        null=True,
        blank=True,
    )
    heating_capacity = models.DecimalField(
        _("Heating Capacity"),
        max_digits=15,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        null=True,
        blank=True,
    )
    heating_unit = models.CharField(
        _("Heating Unit"),
        max_length=20,
        choices=[c for c in Unit.choices if c[0] in (Unit.KW)],
        null=True,
        blank=True,
    )
    cooling_type = models.CharField(
        _("Coolingting Type"),
        max_length=50,
        choices=CoolingType.choices,
        null=True,
        blank=True,
    )
    cooling_capacity = models.DecimalField(
        _("Heating Capacity"),
        max_digits=15,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        null=True,
        blank=True,
    )
    cooling_unit = models.CharField(
        _("Cooling Unit"),
        max_length=20,
        choices=[c for c in Unit.choices if c[0] in (Unit.KW, Unit.TR)],
        null=True,
        blank=True,
    )
    ventilation_type = models.CharField(
        _("Ventilation Type"),
        max_length=50,
        choices=VentilationType.choices,
        null=True,
        blank=True,
    )
    ventilation_capacity = models.DecimalField(
        _("Ventilation Capacity"),
        max_digits=15,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        null=True,
        blank=True,
    )
    ventilation_unit = models.CharField(
        _("Ventilation Unit"),
        max_length=20,
        choices=[c for c in Unit.choices if c[0] in (Unit.M3_H, Unit.CFM)],
        null=True,
        blank=True,
    )
    lighting_type = models.CharField(
        _("Lighting Type"),
        max_length=50,
        choices=LightingType.choices,
        null=True,
        blank=True,
    )
    lighting_capacity = models.DecimalField(
        _("Lighting Capacity"),
        max_digits=15,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        null=True,
        blank=True,
    )
    lighting_unit = models.CharField(
        _("Lighting Unit"),
        max_length=20,
        choices=[c for c in Unit.choices if c[0] in (Unit.KW)],
        null=True,
        blank=True,
    )

    class Meta:
        abstract = True  # This ensures it won't create its own table.


class Building(BaseModel, BaseGeoModel, BuildingOperationalInfo):
    name = models.CharField(_("Building name/code"), max_length=255)
    structural_components = models.ManyToManyField(
        Assembly,
        blank=True,
        related_name="buildings",
        through="BuildingAssembly",
    )
    simulated_components = models.ManyToManyField(
        Assembly,
        blank=True,
        related_name="buildingsimulations",
        through="BuildingAssemblySimulated",
    )
    category = models.ForeignKey(
        CategorySubcategory, on_delete=models.SET_NULL, null=True, blank=True
    )
    construction_year = models.IntegerField(
        _("Year of Construction"),
        null=True,
        blank=True,
    )
    climate_zone = models.CharField(
        _("Climate"), choices=ClimateZone.choices, max_length=50
    )
    total_floor_area = models.DecimalField(
        _("Total Floor Area"),
        help_text=_("Gross floor area [m²]"),
        max_digits=10,
        decimal_places=2,
        null=False,
        blank=False,
    )
    cond_floor_area = models.DecimalField(
        _("Conditioned Floor Area"),
        help_text=_("Gross floor area [m²]"),
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
    )
    floors_above_ground = models.IntegerField(
        _("Floors above ground"),
        help_text=_("Number of floors above"),
        validators=[MaxValueValidator(1000)],
        null=True,
        blank=True,
    )
    floors_below_ground = models.IntegerField(
        _("Floors below ground"),
        help_text=_("Number of floors below"),
        validators=[MaxValueValidator(100)],
        null=True,
        blank=True,
    )
    reference_period = models.IntegerField(
        _("Assessment time frame"),
        help_text=_("Years of building use"),
        null=False,
        blank=False,
        default=50,
    )

    class Meta:
        verbose_name = "Building"
        verbose_name_plural = "Buildings"


class BuildingAssembly(models.Model):
    assembly = models.ForeignKey(Assembly, on_delete=models.CASCADE)
    building = models.ForeignKey(Building, on_delete=models.CASCADE)
    quantity = models.DecimalField(
        _("Quantity"),
        help_text=_("How much of this component"),
        max_digits=10,
        decimal_places=2,
        default=0,
        null=False,
        blank=False,
    )
    reporting_life_cycle = models.IntegerField(
        _("Reporting life-cycle"),
        help_text=_("Reporting life-cycle for assembly"),
        validators=[MinValueValidator(1), MaxValueValidator(10000)],
    )

    class Meta:
        verbose_name = "Building structural component"
        verbose_name_plural = "Building structural components"


class BuildingAssemblySimulated(models.Model):
    assembly = models.ForeignKey(Assembly, on_delete=models.CASCADE)
    building = models.ForeignKey(Building, on_delete=models.CASCADE)
    quantity = models.DecimalField(
        _("Quantity"),
        help_text=_("How many of components"),
        max_digits=10,
        decimal_places=2,
        null=False,
        blank=False,
    )
    unit = models.CharField(
        _("Unit of Quantity"), max_length=20, choices=Unit.choices, default=Unit.UNKNOWN
    )
    reporting_life_cycle = models.IntegerField(
        _("Reporting life-cycle"),
        help_text=_("Reporting life-cycle for assembly"),
        validators=[MinValueValidator(1), MaxValueValidator(10000)],
        default=50,
    )

    class Meta:
        verbose_name = "Building structural component simulation"
        verbose_name_plural = "Building structural components simulation"


class OperationalProduct(BaseProduct):
    """Join Table for EPDs and Building. Products are EPDs with quantity and results."""

    building = models.ForeignKey(
        Building, on_delete=models.CASCADE, related_name="operational_products"
    )

    def get_impacts(self):
        return calculate_impact_operational(self)


class SimulatedOperationalProduct(BaseProduct):
    """Join Table for EPDs and Simulated Building. Products are EPDs with quantity and results."""

    building = models.ForeignKey(
        Building,
        on_delete=models.CASCADE,
        related_name="simulated_operational_products",
    )

    def get_impacts(self):
        return calculate_impact_operational(self)
