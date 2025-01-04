from django.db import models
from django.utils.translation import gettext as _


from .assembly import Assembly
from .base import BaseGeoModel, BaseModel
from .epd import Unit


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
        return f"{self.category.name}: {self.subcategory.name}"


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

    class Meta:
        verbose_name = "Building"
        verbose_name_plural = "Buildings"


class BuildingAssembly(models.Model):
    assembly = models.ForeignKey(
        Assembly, on_delete=models.CASCADE
    )
    building = models.ForeignKey(Building, on_delete=models.CASCADE)
    quantity = models.DecimalField(
        _("Quantity"),
        help_text=_("How much of this component"),
        max_digits=10,
        decimal_places=2,
        default=0
    )

    class Meta:
        verbose_name = "Building structural component"
        verbose_name_plural = "Building structural components"


class BuildingAssemblySimulated(models.Model):
    assembly = models.ForeignKey(
        Assembly, on_delete=models.CASCADE
    )
    building = models.ForeignKey(Building, on_delete=models.CASCADE)
    quantity = models.DecimalField(
        _("Quantity"),
        help_text=_("How many of components"),
        max_digits=10,
        decimal_places=2,
        null=False,
        blank=False,
    )

    class Meta:
        verbose_name = "Building structural component simulation"
        verbose_name_plural = "Building structural components simulation"
