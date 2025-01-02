from django.db import models
from django.utils.translation import gettext as _
from django.core.exceptions import ValidationError

from cities_light.models import Country, City

from .epd import EPD, Unit, Impact
from .base import BaseModel


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
    GENERIC = "generic", "Generic" # "Use for Quick Assessment"
    CUSTOM = "custom", "Custom" # "Use for Detailed Assessment"


class AssemblyDimension(models.TextChoices):
    AREA = "area", "Area (m^2)" # Area-type calculations
    LENGTH = "length", "Length (m)" # Length-type calculations   
    MASS = "mass", "Mass (kg)" # Length-type calculations   
    VOLUME = "volume", "Volume (m^3)" # Length-type calculations   


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
    techniques = models.ManyToManyField(AssemblyTechnique,through="AssemblyCategoryTechnique", related_name="categories" )

    class Meta:
        verbose_name = "Assembly Group"
        verbose_name_plural = "Assembly Groups"

    def __str__(self):
        return f"{self.tag} - {self.name}"


class AssemblyCategoryTechnique(models.Model):
    category = models.ForeignKey(AssemblyCategory, on_delete=models.CASCADE)
    technique = models.ForeignKey(AssemblyTechnique, on_delete=models.CASCADE, null=True, blank=True)
    description = models.TextField(null=True, blank=True)


class Assembly(BaseModel):
    """Structural Element consisting of Products.
    """
    country = models.ForeignKey(
        Country, on_delete=models.SET_NULL, null=True, blank=True
    )
    city = models.ForeignKey(City, on_delete=models.SET_NULL, null=True, blank=True)
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
    classification = models.ForeignKey(
         AssemblyCategoryTechnique, on_delete=models.SET_NULL, null=True, blank=True
    )
    comment = models.TextField(_("Comment"), null=True, blank=True)
    description = models.TextField(_("Description"), null=True, blank=True)
    name = models.CharField(max_length=255)
    products = models.ManyToManyField(
        EPD, blank=True, related_name="assemblies", through="Product"
    )

    def __str__(self):
        return self.name

class Product(models.Model):
    """Join Table for EPDs and Assemblied. Products are EPDs with quantity and results."""
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
    assembly = models.ForeignKey(Assembly, on_delete=models.CASCADE)
    quantity = models.DecimalField(
        _("Quantity of EPD"),
        max_digits=10,
        decimal_places=3,
        null=False,
        blank=False,
    )

    def clean(self):
            """
            Validates that the `unit` matches the expected unit for the chosen `impact_category`.
            """
            super().clean()
            
            def get_dim_info(dimension, declared_unit):
                match (dimension, declared_unit):
                    case (_, Unit.PCS):
                        # 'Pieces' EPD is treated the same across all assembly dimensions
                        selection_text = "Quantity"
                        selection_unit = Unit.PCS
                    case (AssemblyDimension.AREA, _):
                        selection_text = "Layer Thickness"
                        selection_unit = Unit.CM
                    case (AssemblyDimension.VOLUME, _):
                        selection_text = "Share of volume"
                        selection_unit = Unit.PERCENT
                    case (AssemblyDimension.MASS, _):
                        selection_text = "Share of mass"
                        selection_unit = Unit.KG
                    case (AssemblyDimension.LENGTH, _):
                        selection_text = "Share of cross-section"
                        selection_unit = Unit.CM2
                    case _:
                        raise ValueError(
                            f"Unsupported combination: dimension '{dimension}', declared_unit '{declared_unit}'"
                        )
                return selection_unit
            
            expected_unit = get_dim_info(self.assembly.dimension, self.epd.declared_unit)
            if self.input_unit != expected_unit:
                raise ValidationError(
                    {
                        'input_unit': _(
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
        verbose_name = "Product"
        verbose_name_plural = "Products"