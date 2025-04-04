from decimal import Decimal
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.utils.translation import gettext as _

from cities_light.models import Country
from accounts.models import CustomCity

from .base import BaseModel



INDICATOR_UNIT_MAPPING = {
    "pere": "mj",
    "perm": "mj",
    "pert": "mj",
    "penre": "mj",
    "penrm": "mj",
    "penrt": "mj",
    "sm": "kg",
    "sf": "mj",
    "nrsf": "mj",
    "fw": "m³",
    "hwd": "kg",
    "nhwd": "kg",
    "rwd": "kg",
    "cru": "kg",
    "mfr": "kg",
    "mer": "kg",
    "eee": "mj",
    "eet": "mj",
    "gwp": "kgco2e",
    "gwp-bio": "kgco2e",
    "gwp-fos": "kgco2e",
    "gwp-lul": "kgco2e",
    "odp": "kgcfc11e",
    "pocp": "kgnmvoce",
    "ap": "moleh+e",  # Mole of H+ eq.
    "ep-terrestrial": "molene",  # Mole of N eq.
    "ep-freshwater": "kgpe",  # kg P eq.
    "ep-marine": "kgne",  # kg N eq.
    "wdp": "m3we",  # m³ world equiv.
    "adpe": "kgsbe",  # kg Sb eq.
    "adpf": "mj",
}


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
    conversions = models.JSONField(_("Conversions for units, follwoing EPDx"))
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
    unit = models.CharField(
        _("Impact Unit"), max_length=20, choices=Unit.choices, default=Unit.UNKNOWN
    )

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
        validators=[MinValueValidator(Decimal('0.01'))],
        null=False,
        blank=False,
    )

    def __str__(self):
        return self.name

    def get_gwp_impact_sum(self):
        impacts = EPDImpact.objects.filter(
            epd=self, impact__impact_category="gwp", impact__life_cycle_stage="a1a3"
        )
        return round(sum(impact.value for impact in impacts), 2)

    def get_penrt_impact_sum(self):
        impacts = EPDImpact.objects.filter(
            epd=self, impact__impact_category="penrt", impact__life_cycle_stage="a1a3"
        )
        return round(sum(impact.value for impact in impacts), 2)


class EPDImpact(models.Model):
    """Join Table for EPDs and Impact"""

    epd = models.ForeignKey(EPD, on_delete=models.CASCADE)
    impact = models.ForeignKey(Impact, on_delete=models.CASCADE)
    value = models.FloatField()

    class Meta:
        unique_together = ("epd", "impact")
