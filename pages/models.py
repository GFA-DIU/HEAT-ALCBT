from django.db import models
from django.utils.translation import gettext as _

from cities_light.models import Country, City

from accounts.models import CustomUser


class BaseModel(models.Model):
    created_by = models.ForeignKey(
        CustomUser, on_delete=models.SET_NULL, null=True, blank=True
    )
    created_at = models.DateTimeField(_("Created at"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Updated at"), auto_now=True)
    public = models.BooleanField(
        _("Public"), help_text=_("Is it visible to all roles"), default=False
    )
    draft = models.BooleanField(
        _("Draft"), help_text=_("Is it still a draft"), default=False
    )


class MaterialCategory(BaseModel):
    name = models.CharField(_("Name"), max_length=255)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Material category"
        verbose_name_plural = "Material categories"


class Material(BaseModel):
    name = models.CharField(_("Marerial name"), max_length=255)
    country = models.ForeignKey(
        Country, on_delete=models.SET_NULL, null=True, blank=True
    )
    city = models.ForeignKey(City, on_delete=models.SET_NULL, null=True, blank=True)
    density = models.DecimalField(
        _("Density"),
        help_text=_("Unit is Kg/m³"),
        max_digits=10,
        decimal_places=3,
        null=False,
        blank=False,
    )
    emissions = models.DecimalField(
        _("Emissions"),
        help_text=_("Unit is co²/kg"),
        max_digits=10,
        decimal_places=3,
        null=False,
        blank=False,
    )
    category = models.ForeignKey(
        MaterialCategory, on_delete=models.SET_NULL, null=True, blank=True
    )

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Material"
        verbose_name_plural = "Materials"


class StructuralComponent(BaseModel):
    name = models.CharField(_("Structural component name"), max_length=255)
    country = models.ForeignKey(
        Country, on_delete=models.SET_NULL, null=True, blank=True
    )
    city = models.ForeignKey(City, on_delete=models.SET_NULL, null=True, blank=True)
    surface = models.DecimalField(
        _("Surface"),
        help_text=_("Unit is m²"),
        max_digits=10,
        decimal_places=3,
        null=False,
        blank=False,
    )
    materials = models.ManyToManyField(
        Material,
        blank=True,
        related_name="structural_components",
        through="StructuralComponentMaterial",
    )

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Structural component"
        verbose_name_plural = "Structural components"


class StructuralComponentMaterial(models.Model):
    material = models.ForeignKey(Material, on_delete=models.CASCADE)
    structural_component = models.ForeignKey(
        StructuralComponent, on_delete=models.CASCADE
    )
    volume = models.DecimalField(
        _("Volume"),
        help_text=_("Unit is m³"),
        max_digits=10,
        decimal_places=3,
        null=False,
        blank=False,
    )
    weight = models.DecimalField(
        _("Weight"),
        help_text=_("Unit is kg"),
        max_digits=10,
        decimal_places=3,
        null=False,
        blank=False,
    )
    area = models.DecimalField(
        _("Area"),
        help_text=_("Unit is m²"),
        max_digits=10,
        decimal_places=3,
        null=False,
        blank=False,
    )
    thickness = models.DecimalField(
        _("Thickness"),
        help_text=_("Unit is m"),
        max_digits=10,
        decimal_places=3,
        null=False,
        blank=False,
    )

    class Meta:
        verbose_name = "Structural component material"
        verbose_name_plural = "Structural component materials"


class BuildingSubcategory(BaseModel):
    name = models.CharField(_("Name"), max_length=255)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Building subcategory"
        verbose_name_plural = "Building subcategories"


class BuildingCategory(BaseModel):
    name = models.CharField(_("Name"), max_length=255)
    subcategories = models.ManyToManyField(
        BuildingSubcategory, blank=True, related_name="categories"
    )

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Building category"
        verbose_name_plural = "Building categories"


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
        StructuralComponent,
        blank=True,
        related_name="buildings",
        through="BuildingStructuralComponent",
    )
    category = models.ForeignKey(
        BuildingCategory, on_delete=models.SET_NULL, null=True, blank=True
    )
    subcategory = models.ForeignKey(
        BuildingSubcategory, on_delete=models.SET_NULL, null=True, blank=True
    )

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Structural component"
        verbose_name_plural = "Structural components"


class BuildingStructuralComponent(models.Model):
    structural_component = models.ForeignKey(
        StructuralComponent, on_delete=models.CASCADE
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
