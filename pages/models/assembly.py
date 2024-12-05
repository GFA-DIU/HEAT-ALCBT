from django.db import models
from django.utils.translation import gettext as _

from cities_light.models import Country, City

from .epd import EPD, Unit, Impact
from .base import BaseModel


class AssemblyType(models.TextChoices):
    """Adopted from LCAx."""
    GENERIC = "generic", "Use for Quick Assessment"
    CUSTOM = "custom", "Use for Detailed Assessment"


class AssemblySubCategory(models.Model):
    """
    Represents an individual assembly category within a group.
    """
    name = models.CharField(max_length=255)
    numeric_identifier = models.PositiveIntegerField()  # To preserve order (e.g., 1, 2, 3, etc.)

    class Meta:
        ordering = ["numeric_identifier"]  # Default ordering by order field
        verbose_name = "Assembly Subcategorie"
        verbose_name_plural = "Assembly Subcategories"

    def __str__(self):
        return f"{self.group.name} / {self.name}"


class AssemblyCategory(models.Model):
    """
    Represents a group of assemblies, e.g., 'Bottom Floor Construction'.
    """
    name = models.CharField(max_length=255, unique=True)
    subcategories = models.ManyToManyField(AssemblySubCategory,through="AssemblyCategorySubcategory", related_name="categories" )

    class Meta:
        verbose_name = "Assembly Group"
        verbose_name_plural = "Assembly Groups"

    def __str__(self):
        return self.name


class AssemblyCategorySubcategory(models.Model):
    category = models.ForeignKey(AssemblyCategory, on_delete=models.CASCADE)
    subcategory = models.ForeignKey(AssemblySubCategory, on_delete=models.CASCADE)
    description = models.TextField()


class Product(models.Model):
    """Products are EPDs with quantity and results."""
    description = models.CharField(
        _("Description"), max_length=255, null=True, blank=True
    )
    epd = models.ForeignKey(EPD, on_delete=models.CASCADE)
    input_unit = models.CharField(
        _("Unit for quantity of EPD"),
        max_length=20,
        choices=Unit.choices,
        default=Unit.UNKNOWN,
    )

    class Meta:
        verbose_name = "Product"
        verbose_name_plural = "Products"


class Assembly(BaseModel):
    """Structural Element consisting of Products.
    """
    country = models.ForeignKey(
        Country, on_delete=models.SET_NULL, null=True, blank=True
    )
    city = models.ForeignKey(City, on_delete=models.SET_NULL, null=True, blank=True)
    type = models.CharField(
        _("Assembly type"),
        max_length=20,
        choices=AssemblyType.choices,
        default=AssemblyType.CUSTOM,
    )
    classification = models.ForeignKey(
         AssemblyCategorySubcategory, on_delete=models.SET_NULL, null=True, blank=True
    )
    comment = models.TextField(_("Comment"))
    description = models.TextField(_("Description"))
    name = models.CharField(max_length=255)
    products = models.ManyToManyField(
        Product, blank=True, related_name="assemblies", through="AssemblyProduct"
    )
    impacts = models.ManyToManyField(Impact, blank=False, related_name="assemblies", through="AssemblyImpact")


class AssemblyProduct(models.Model):
    """Join table for Product and Assembly."""
    assembly = models.ForeignKey(Assembly, on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.DecimalField(
        _("Quantity of EPD"),
        max_digits=10,
        decimal_places=3,
        null=False,
        blank=False,
    )

    class Meta:
        verbose_name = "Assembly Product"
        verbose_name_plural = "Assembly Products"


class AssemblyImpact(models.Model):
    """Join Table for Assemblies and Impact"""
    assembly = models.ForeignKey(Assembly, on_delete=models.CASCADE)
    impact = models.ForeignKey(Impact, on_delete=models.CASCADE)
    value = models.FloatField()    