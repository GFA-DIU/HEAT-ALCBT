from decimal import Decimal
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.utils.translation import gettext as _

from cities_light.models import Country
from accounts.models import CustomCity

from .base import BaseModel


class Unit(models.TextChoices):
    """Adapted from LCAx."""

    CM = "cm", "Centimeter"
    M = "m", "Meter"
    CM2 = "cm2", "Square Centimeter"
    M2 = "m2", "Square Meter"
    M3 = "m3", "Cubic Meter"
    KG = "kg", "Kilogram"
    TONES = "tones", "Tones"
    PCS = "pcs", "Pieces"
    KWH = "kwh", "Kilowatt Hour"
    L = "l", "Liter"
    M2R1 = "m2r1", "Square Meter Rate 1"
    KM = "km", "Kilometer"
    TONES_KM = "tones_km", "Tones per Kilometer"
    KGM3 = "kgm3", "Kilogram per Cubic Meter"
    UNKNOWN = "unknown", "Unknown"
    PERCENT = "percent", "Percent"
    ## added from OEKOBAUDAT
    MJ = "mj", "Megajoule"
    KGCO2E = "kgco2e", "kgCO2e"
    KFCFC11E = "kgcfc11e", "kgCFC11e"
    KGNMVOCE = "kgnmvoce", "kg NMVOC eq."
    HPEQ = "moleh+e", "Mole of H+ eq."
    NEQ = "molene", "Mole of N eq."
    KGP = "kgpe", "kg P eq."
    KGN = "kgne", "kg N eq."
    M3WE = "m3we", "m³ world equiv."
    KGSB = "kgsbe", "kg Sb eq."
    ## Operational carbon
    TR = "tr", "Ton of Refrigeration"
    KW = "kw", "Kilowatt"
    M3_H = "m^3/h", "Cubic Meters per Hour"
    CFM = "cfm", "Cubic Feet per Minute"
    CELSIUS = "celsius", "°Celsius"
    FAHRENHEIT = "fahrenheit", "°Fahrenheit"
    LITER = "liter", "Liter"


INDICATOR_UNIT_MAPPING = {
    "pere": Unit.MJ,
    "perm": Unit.MJ,
    "pert": Unit.MJ,
    "penre": Unit.MJ,
    "penrm": Unit.MJ,
    "penrt": Unit.MJ,
    "sm": Unit.KG,
    "sf": Unit.MJ,
    "nrsf": Unit.MJ,
    "fw": Unit.M3,
    "hwd": Unit.KG,
    "nhwd": Unit.KG,
    "rwd": Unit.KG,
    "cru": Unit.KG,
    "mfr": Unit.KG,
    "mer": Unit.KG,
    "eee": Unit.MJ,
    "eet": Unit.MJ,
    "gwp": Unit.KGCO2E,
    "gwp-bio": Unit.KGCO2E,
    "gwp-fos": Unit.KGCO2E,
    "gwp-lul": Unit.KGCO2E,
    "odp": Unit.KFCFC11E,
    "pocp": Unit.KGNMVOCE,
    "ap": Unit.HPEQ,  # Mole of H+ eq.
    "ep-terrestrial": Unit.NEQ,  # Mole of N eq.
    "ep-freshwater": Unit.KGP,  # kg P eq.
    "ep-marine": Unit.KGN,  # kg N eq.
    "wdp": Unit.M3WE,  # m³ world equiv.
    "adpe": Unit.KGSB,  # kg Sb eq.
    "adpf": Unit.MJ,
}


class ImpactCategoryKey(models.TextChoices):
    """Taken from LCAx."""

    GWP = "gwp", "Global Warming Potential"
    GWP_FOS = "gwp_fos", "Global Warming Potential - Fossil"
    GWP_BIO = "gwp_bio", "Global Warming Potential - Biogenic"
    GWP_LUL = "gwp_lul", "Global Warming Potential - Land Use and Land Use Change"
    ODP = "odp", "Ozone Depletion Potential"
    AP = "ap", "Acidification Potential"
    EP = "ep", "Eutrophication Potential"
    EP_FW = "ep_fw", "Eutrophication Potential - Freshwater"
    EP_MAR = "ep_mar", "Eutrophication Potential - Marine"
    EP_TER = "ep_ter", "Eutrophication Potential - Terrestrial"
    POCP = "pocp", "Photochemical Ozone Creation Potential"
    ADPE = "adpe", "Abiotic Depletion Potential - Elements"
    ADPF = "adpf", "Abiotic Depletion Potential - Fossil Fuels"
    PENRE = "penre", "Primary Energy Non-Renewable"
    PERE = "pere", "Primary Energy Renewable"
    PERM = "perm", "Primary Energy Renewable Material"
    PERT = "pert", "Primary Energy Renewable Total"
    PENRT = "penrt", "Primary Energy Non-Renewable Total"
    PENRM = "penrm", "Primary Energy Non-Renewable Material"
    SM = "sm", "Secondary Material"
    PM = "pm", "Particulate Matter"
    WDP = "wdp", "Water Deprivation Potential"
    IRP = "irp", "Ionizing Radiation Potential"
    ETP_FW = "etp_fw", "Eco-Toxicity Potential - Freshwater"
    HTP_C = "htp_c", "Human Toxicity Potential - Cancer"
    HTP_NC = "htp_nc", "Human Toxicity Potential - Non-Cancer"
    SQP = "sqp", "Soil Quality Potential"
    RSF = "rsf", "Renewable Secondary Fuels"
    NRSF = "nrsf", "Non-Renewable Secondary Fuels"
    FW = "fw", "Freshwater Use"
    HWD = "hwd", "Hazardous Waste Disposed"
    NHWD = "nhwd", "Non-Hazardous Waste Disposed"
    RWD = "rwd", "Radioactive Waste Disposed"
    CRU = "cru", "Components for Reuse"
    MRF = "mrf", "Materials for Recycling"
    MER = "mer", "Materials for Energy Recovery"
    EEE = "eee", "Exported Energy Electricity"
    EET = "eet", "Exported Energy Thermal"


class LifeCycleStage(models.TextChoices):
    """Adopted from LCAx."""

    A0 = "a0", "Stage A0"
    A1A3 = "a1a3", "Stages A1 to A3"
    A4 = "a4", "Stage A4"
    A5 = "a5", "Stage A5"
    B1 = "b1", "Stage B1"
    B2 = "b2", "Stage B2"
    B3 = "b3", "Stage B3"
    B4 = "b4", "Stage B4"
    B5 = "b5", "Stage B5"
    B6 = "b6", "Stage B6"
    B7 = "b7", "Stage B7"
    B8 = "b8", "Stage B8"
    C1 = "c1", "Stage C1"
    C2 = "c2", "Stage C2"
    C3 = "c3", "Stage C3"
    C4 = "c4", "Stage C4"
    D = "d", "Stage D"


class EPDType(models.TextChoices):
    """Adopted from LCAx."""

    OFFICIAL = "official", "From a verified ILCD+EPD source"
    CUSTOM = "custom", "Created by user"
    GENERIC = "generic", "Representative EPD for a country"


class epdLCAx(models.Model):
    """
    Fields parsed through LCAx.
    """

    comment = models.CharField(_("Comment"), max_length=255, null=True, blank=True)
    conversions = models.JSONField(_("Conversions for units, follwoing EPDx"), null=True, blank=True)
    declared_unit = models.CharField(
        _("Declared Unit"), max_length=20, choices=Unit.choices, default=Unit.UNKNOWN
    )
    UUID = models.CharField(_("Unique worldwide EPD identifier"), max_length=40)
    name = models.CharField(_("Material name"), max_length=255)
    names = models.JSONField(
        _("Name translations")
    )  # list[{"value": str, "lang": str}]
    version = models.CharField(
        _("EPD Node Version"), max_length=255, null=True, blank=True
    )

    class Meta:
        unique_together = ("UUID", "name")
        abstract = True  # This ensures it won't create its own table.


class MaterialCategory(models.Model):
    """
    Model to represent hierarchical material categories
    """

    name_de = models.CharField(max_length=255, null=False, blank=True)
    name_en = models.CharField(max_length=255, null=False, blank=True)
    category_id = models.CharField(max_length=10, null=False, unique=True)
    level = models.PositiveIntegerField()
    parent = models.ForeignKey(
        "self", null=True, blank=True, related_name="children", on_delete=models.CASCADE
    )

    def __str__(self):
        return self.name_en


class Impact(models.Model):
    impact_category = models.CharField(
        _("Impact Category"), max_length=20, choices=ImpactCategoryKey.choices
    )
    life_cycle_stage = models.CharField(
        _("Life Cycle Stage"), max_length=20, choices=LifeCycleStage.choices
    )

    class Meta:
        unique_together = ("impact_category", "life_cycle_stage")

    @property
    def unit(self):
        return INDICATOR_UNIT_MAPPING[self.impact_category]

    def clean(self):
        """
        Validates that the `unit` matches the expected unit for the chosen `impact_category`.
        """
        super().clean()
        expected_unit = INDICATOR_UNIT_MAPPING.get(self.impact_category)
        if expected_unit and self.unit != expected_unit:
            raise ValidationError(
                {
                    "unit": _(
                        f"The unit '{self.unit}' is not valid for the impact category '{self.impact_category}'. "
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

    def __str__(self):
        return f"{self.impact_category} {self.life_cycle_stage}"


class Label(models.Model):
    SCALE_TYPE_CHOICES = [
        ('nominal', 'Unordered categories (nominal)'),
        ('ordinal',  'Ordered categories (ordinal)'),
        ('cardinal',  'Numeric (interval/ratio)'),
    ]

    name = models.CharField(max_length=255, unique=True)
    source = models.CharField(_("Source"), max_length=255, null=True, blank=True)
    comment = models.CharField(_("Comment"), max_length=255, null=True, blank=True)
    scale_type  = models.CharField(_("Scale Type"), max_length=10, choices=SCALE_TYPE_CHOICES)
    scale_parameters  = models.JSONField(_("Scale Parameters"),blank=True, null=True, help_text=_("Scale-specific metadata"))  # list of tuples
    
    def clean(self):
        super.clean()
        if not isinstance(self.scale_parameters, list):
            raise ValidationError("Scale Parameters must be a list.")
        
    def save(self, *args, **kwargs):
        """
        Override save to include clean validation.
        """
        self.clean()
        super().save(*args, **kwargs)


class EPD(BaseModel, epdLCAx):
    """EPDs are the material information from official databases."""

    # material_category
    country = models.ForeignKey(
        Country, on_delete=models.SET_NULL, null=True, blank=True
    )
    impacts = models.ManyToManyField(
        Impact, blank=False, related_name="related_epds", through="EPDImpact"
    )
    city = models.ForeignKey(
        CustomCity, on_delete=models.SET_NULL, null=True, blank=True
    )
    category = models.ForeignKey(
        MaterialCategory, on_delete=models.SET_NULL, null=True, blank=True
    )
    source = models.CharField(_("Source"), max_length=255, null=True, blank=True)
    type = models.CharField(_("Type"), choices=EPDType.choices, max_length=255)
    declared_amount = models.DecimalField(
        _("Reference Quantity of EPD"),
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
        null=False,
        blank=False,
    )
    labels = models.ManyToManyField(
        Label, blank=True, related_name="epd_labels", through="EPDLabel"
    )

    def __str__(self):
        return self.name

    def get_gwp_impact_sum(self, life_cycle_stage):
        impact = EPDImpact.objects.get(
            epd=self,
            impact__impact_category="gwp",
            impact__life_cycle_stage=life_cycle_stage,
        )
        return Decimal(round(impact.value, 2)) / self.declared_amount

    def get_penrt_impact_sum(self, life_cycle_stage):
        impact = EPDImpact.objects.get(
            epd=self,
            impact__impact_category="penrt",
            impact__life_cycle_stage=life_cycle_stage,
        )
        return Decimal(round(impact.value, 2)) / self.declared_amount

    def get_available_units(self):
        units = {self.declared_unit}
        if self.declared_unit not in [Unit.KG, Unit.M3, Unit.KWH]:
            return list(units)
        for item in self.conversions:
            match (self.declared_unit, item.get("unit")):
                case (Unit.KWH | Unit.M3, "kg" | "-"):
                    units.add(Unit.KG)
                case (Unit.KWH, "kg/m^3"):
                    units.update({Unit.M3, Unit.LITER})
                case (Unit.M3 | Unit.KG, "kg/m^3"):
                    units.update({Unit.M3, Unit.KG})
                case (_, _):
                    Warning(
                        "The epd (%s) has a conversion %s for which there is not corresponding unit.",
                        self.id,
                        item.get("unit"),
                    )
        return units


class EPDImpact(models.Model):
    """Join Table for EPDs and Impact"""

    epd = models.ForeignKey(EPD, on_delete=models.CASCADE)
    impact = models.ForeignKey(Impact, on_delete=models.CASCADE)
    value = models.FloatField()

    class Meta:
        unique_together = ("epd", "impact")


class EPDLabel(models.Model):
    """Join Table for EPDs and Label"""
    
    epd = models.ForeignKey(EPD, on_delete=models.CASCADE)
    label = models.ForeignKey(Label, on_delete=models.CASCADE)
    score = models.CharField(
        _("Score"), max_length=255, blank=False, null=False
    )
    comment = models.CharField(_("Comment"), max_length=255, null=True, blank=True)
    
    class Meta:
        unique_together = ("epd", "label")
    
    
    def clean(self):
        super().clean()
        valid_options = list(self.label.scale_parameters)
        if not self.score in valid_options:
            raise ValidationError(
                f"Label score {self.score} needs to be in Scale Parameters: {self.label.scale_parameters}."
            )


    def save(self, *args, **kwargs):
        """
        Override save to include clean validation.
        """
        self.clean()
        super().save(*args, **kwargs)