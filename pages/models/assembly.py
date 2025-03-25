from django.db import models
from django.utils.translation import gettext as _
from django.core.exceptions import ValidationError

from cities_light.models import Country
from accounts.models import CustomCity

from .epd import EPD, Unit
from .base import BaseModel
from .product import BaseProduct


class AssemblyMode(models.TextChoices):
    """Part of default or not.

    Adapted from LCAx, where it's used for EPDs.
    ```Python
    class SubType(Enum):
        generic = 'generic'
        specific = 'specific'
        industry = 'industry'
        representative = 'representative'
    ```
    """

    GENERIC = "generic", "Generic"  # "Use for Quick Assessment"
    CUSTOM = "custom", "Custom"  # "Use for Detailed Assessment"


DIMENSION_UNIT_MAPPING = {
    "area": "m^2",
    "length": "m",
    "mass": "kg",
    "volume": "m^3",
}


class AssemblyDimension(models.TextChoices):
    AREA = "area", "m²"  # Area-type calculations
    LENGTH = "length", "m"  # Length-type calculations
    MASS = "mass", "kg"  # Length-type calculations
    VOLUME = "volume", "m³"  # Length-type calculations


class AssemblyTechnique(models.Model):
    """
    Represents an individual assembly category within a group.
    """

    name = models.CharField(max_length=255)

    class Meta:
        # ordering = ["numeric_identifier"]  # Default ordering by order field
        verbose_name = "Assembly Subcategorie"
        verbose_name_plural = "Assembly Subcategories"

    def __str__(self):
        return self.name


class AssemblyCategory(models.Model):
    """
    Represents a group of assemblies, e.g., 'Bottom Floor Construction'.
    """

    name = models.CharField(max_length=255, unique=True)
    tag = models.CharField(max_length=50)
    techniques = models.ManyToManyField(
        AssemblyTechnique,
        through="AssemblyCategoryTechnique",
        related_name="categories",
    )

    class Meta:
        verbose_name = "Assembly Group"
        verbose_name_plural = "Assembly Groups"

    def __str__(self):
        return f"{self.tag} - {self.name}"


class AssemblyCategoryTechnique(models.Model):
    category = models.ForeignKey(AssemblyCategory, on_delete=models.CASCADE)
    technique = models.ForeignKey(
        AssemblyTechnique, on_delete=models.CASCADE, null=True, blank=True
    )
    description = models.TextField(null=True, blank=True)


class Assembly(BaseModel):
    """Structural Element consisting of Products."""

    country = models.ForeignKey(
        Country, on_delete=models.SET_NULL, null=True, blank=True
    )
    city = models.ForeignKey(
        CustomCity, on_delete=models.SET_NULL, null=True, blank=True
    )
    mode = models.CharField(
        _("Assembly Mode"),
        max_length=20,
        choices=AssemblyMode.choices,
        default=AssemblyMode.CUSTOM,
    )
    dimension = models.CharField(
        _("Assembly type"),
        max_length=20,
        choices=AssemblyDimension.choices,
        default=AssemblyDimension.AREA,
    )

    comment = models.TextField(_("Comment"), null=True, blank=True)
    description = models.TextField(_("Description"), null=True, blank=True)
    name = models.CharField(max_length=255)
    products = models.ManyToManyField(
        EPD, blank=True, related_name="assemblies", through="StructuralProduct"
    )
    is_boq = models.BooleanField(default=False)

    def __str__(self):
        return self.name

    @property
    def classification(self):
        """Return the classification of the assembly from the epds."""
        product = self.product_set.first()  # Access Product instances
        return product.classification if product else None


class StructuralProduct(BaseProduct):
    """Join Table for EPDs and Assemblies. Products are EPDs with quantity and results."""

    assembly = models.ForeignKey(Assembly, on_delete=models.CASCADE)

    def clean(self):
        """
        Validates that the `unit` matches the expected unit for the chosen `impact_category`.
        """
        super().clean()

        from pages.views.assembly.epd_filtering import get_epd_info

        dimension = None if self.assembly.is_boq else self.assembly.dimension
        _, expected_unit = get_epd_info(dimension, self.epd.declared_unit)
        if self.input_unit != expected_unit:
            raise ValidationError(
                {
                    "input_unit": (
                        f"The unit '{self.input_unit}' is not valid for the epd '{self.epd.name}'. "
                        f"Expected unit: '{expected_unit}'."
                    )
                }
            )

    def save(self, *args, **kwargs):
        """
        Override save to include clean validation.
        """
        self.clean()
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = "StructuralProduct"
        verbose_name_plural = "StructuralProducts"
