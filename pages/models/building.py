from django.db import models
from django.utils.translation import gettext as _
from django.core.validators import MinValueValidator, MaxValueValidator

from .assembly import Assembly
from .base import BaseGeoModel, BaseModel
from .epd import Unit


class ClimateZone(models.TextChoices):
    HOT_DRY = "hot-dry", "hot-dry"
    WARM_HUMID = "warm-humid", "warm-humid"
    COMPOSITE = "composite", "composite"
    TEMPERATE = "temperate", "temperate"
    COLD = "cold", "cold"


class BuildingSubcategory(models.Model):
    name = models.CharField(_("Name"), max_length=255)

    def __str__(self):
        return f"{self.name}"

    class Meta:
        verbose_name = "Building subcategory"
        verbose_name_plural = "Building subcategories"


class BuildingCategory(models.Model):
    name = models.CharField(_("Name"), max_length=255)
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


class Building(BaseModel, BaseGeoModel):
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
        help_text=_("Gross floor area [m^2]"),
        max_digits=10,
        decimal_places=2,
        null=False,
        blank=False,
    )
    cond_floor_area = models.DecimalField(
        _("Conditioned Floor Area"),
        help_text=_("Gross floor area [m^2]"),
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
        _("Ref. period"),
        help_text=_("Number of years of building usage"),
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
