from django.db import models
from django.utils.translation import gettext as _

from cities_light.models import Country, City

from .assembly import Assembly
from .base import BaseModel


class BuildingSubcategory(models.Model):
    name = models.CharField(_("Name"), max_length=255)

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


class Building(BaseModel):
    name = models.CharField(_("Building name/code"), max_length=255)
    country = models.ForeignKey(
        Country, on_delete=models.SET_NULL, null=True, blank=True
    )
    city = models.ForeignKey(City, on_delete=models.SET_NULL, null=True, blank=True)
    street = models.CharField(_("Street"), max_length=255)
    number = models.IntegerField(_("Number"))
    zip = models.IntegerField(_("ZIP"))
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
        verbose_name = "Structural component"
        verbose_name_plural = "Structural components"


class BuildingAssembly(models.Model):
    assembly = models.ForeignKey(
        Assembly, on_delete=models.CASCADE
    )
    building = models.ForeignKey(Building, on_delete=models.CASCADE)
    quantity = models.DecimalField(
        _("Quantity"),
        help_text=_("How many of components"),
        max_digits=10,
        decimal_places=3,
        null=False,
        blank=False,
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
        decimal_places=3,
        null=False,
        blank=False,
    )

    class Meta:
        verbose_name = "Building structural component"
        verbose_name_plural = "Building structural components"
