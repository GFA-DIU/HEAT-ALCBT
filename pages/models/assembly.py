from django.db import models, transaction
from django.utils.translation import gettext as _
from django.core.exceptions import ValidationError

from cities_light.models import Country
from accounts.models import CustomCity

from .epd import EPD
from .base import BaseModel
from .product import BaseProduct

from django.db.models.signals import post_save
from django.dispatch import receiver


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

    name = models.CharField(max_length=255, unique=True)

    class Meta:
        # ordering = ["numeric_identifier"]  # Default ordering by order field
        verbose_name = "Assembly Subcategorie"
        verbose_name_plural = "Assembly Subcategories"

    def __str__(self):
        return self.name

class AssemblyCategoryManager(models.Manager):
    """Custom manager to auto-create a null technique join."""
    @transaction.atomic
    def create(self, **kwargs):
        category = super().create(**kwargs)
        AssemblyCategoryTechnique.objects.get_or_create(
            category=category,
            technique=None,
            defaults={"description": None},
        )
        return category

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

    def __str__(self):
        tech = self.technique if self.technique else "No Technique"
        return f"{self.category}/ {tech}"

    class Meta:
        unique_together = ("category", "technique")

# Signal: auto-create a (category, null) join when new category is added
@receiver(post_save, sender=AssemblyCategory)
def create_null_join_for_category(sender, instance, created, **kwargs):
    if created:
        AssemblyCategoryTechnique.objects.get_or_create(
            category=instance,
            technique=None,
            defaults={"description": None},
        )

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
    is_template = models.BooleanField(
        _("Use as template"),
        default=False,
        help_text=_("Mark this assembly as a template that can be reused in other buildings")
    )

    def __str__(self):
        return self.name

    def copy_as_template_instance(self, new_name=None, user=None):
        """
        Create a copy of this assembly for use in a building (non-template instance).
        """
        # Create new assembly instance
        new_assembly = Assembly(
            country=self.country,
            city=self.city,
            mode=self.mode,
            dimension=self.dimension,
            comment=self.comment,
            description=self.description,
            name=new_name or f"{self.name} (Copy)",
            is_boq=self.is_boq,
            is_template=False,  # New instance is not a template
        )
        
        if user:
            new_assembly.created_by = user
            
        new_assembly.save()
        
        # Copy all structural products
        for structural_product in self.structuralproduct_set.all():
            StructuralProduct.objects.create(
                epd=structural_product.epd,
                classification=structural_product.classification,
                assembly=new_assembly,
                input_unit=structural_product.input_unit,
                quantity=structural_product.quantity,
                description=structural_product.description,
            )
        
        return new_assembly

    @property
    def classification(self):
        # 1) do we already have a .products list from prefetch?
        prods = getattr(self, "prefetched_products", None)
        if prods is not None:
            # we do – just grab the first one (or None)
            first = prods[0] if prods else None
        else:
            # we don’t – fall back to a single‐query lookup
            first = (
                self.structuralproduct_set
                    .select_related("classification")
                    .first()
            )
        return first.classification if first else None


class StructuralProduct(BaseProduct):
    """Join Table for EPDs and Assemblies. Products are EPDs with quantity and results."""

    classification = models.ForeignKey(
        AssemblyCategoryTechnique, on_delete=models.SET_NULL, null=True, blank=True
    )
    assembly = models.ForeignKey(Assembly, on_delete=models.CASCADE)

    def clean(self):
        """
        Validates that the `unit` matches the expected unit for the chosen `impact_category`.
        """
        super().clean()

        dimension = None if self.assembly.is_boq else self.assembly.dimension
        _, expected_units = self.epd.get_epd_info(dimension)
        if self.input_unit not in expected_units:
            raise ValidationError(
                {
                    "input_unit": (
                        f"The unit '{self.input_unit}' is not valid for the epd '{self.epd.name}'. "
                        f"Expected unit: '{expected_units}'."
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
