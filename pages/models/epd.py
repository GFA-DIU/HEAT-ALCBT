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
    TON = "ton", "Ton"
    PCS = "pcs", "Pieces"
    KWH = "kwh", "Kilowatt Hour"
    L = "l", "Liter"
    M2R1 = "m2r1", "Square Meter Rate 1"
    KM = "km", "Kilometer"
    TON_KM = "ton_km", "Ton per Kilometer"
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
    OFFICIAL_NON_STANDARD = "official_non_standard", "Official from non ILCD + EPD format"
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
    
    def __str__(self):
        return self.name


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

    # --- nomenclature -----------------------------------------------------
    # `name` arrived from a dozen different importers and carries whatever the
    # source document happened to be titled: sometimes the material ("Gypsum"),
    # sometimes a trade name alone ("MU-307", "Xtend"), sometimes the maker
    # buried mid-string ("Shutters - clauss markisen Projekt GmbH - Fire
    # curtain"), sometimes a 227-character specification dump. A user searching
    # "cement" never finds MU-307, which is a cement.
    #
    # These split the parts out so the label can be composed instead of
    # hand-written, and so search and sort work on the right thing. All are
    # optional: a record with none of them behaves exactly as before.
    material_name = models.CharField(
        _("Material"), max_length=255, null=True, blank=True,
        help_text=_("What the product is, independent of brand. Drives search and sorting."),
    )
    product_name = models.CharField(
        _("Product / trade name"), max_length=255, null=True, blank=True,
        help_text=_("Manufacturer's name for this specific product, where it has one."),
    )
    manufacturer = models.CharField(
        _("Manufacturer"), max_length=255, null=True, blank=True,
    )
    source_name = models.CharField(
        _("Original title"), max_length=255, null=True, blank=True,
        help_text=_("The title exactly as it appeared in the source document. Kept so a "
                    "figure can always be traced back after the display name changes."),
    )

    type = models.CharField(_("Type"), choices=EPDType.choices, max_length=255)
    declared_amount = models.DecimalField(
        _("Reference Quantity of EPD"),
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
        null=False,
        blank=False,
    )
    class Meta:
        # Overrides epdLCAx.Meta, which keys uniqueness on (UUID, name) only.
        #
        # That was unworkable here: 966 generic EPDs carry a placeholder UUID
        # (two distinct values across all of them), so for those rows the rule
        # collapsed to "unique on name", and the same material could not exist
        # for two countries. The workaround was a trailing space in the name -
        # "Steel reinforcement (steel rebar) " for India beside
        # "Steel reinforcement (steel rebar)" for Cambodia. That made every
        # name-based lookup pick whichever it met first, which is how an import
        # once resolved 1,398 rebar lines to India's factor (2.60) instead of
        # Cambodia's (2.4247), and how an aluminium record with no density was
        # silently valued at zero.
        #
        # The same material in two countries is the normal case, so country
        # belongs in the key.
        unique_together = ("UUID", "name", "country")

    labels = models.ManyToManyField(
        Label, blank=True, related_name="epd_labels", through="EPDLabel"
    )

    def __str__(self):
        return self.display_name

    @property
    def display_name(self):
        """Label shown in the material picker and on reports.

        Material first, so an alphabetical list groups cements together instead
        of scattering them under M, S and X:

            Portland composite cement - MU-307 - PT Cipta Mortar Utama
            Ready-mix concrete C25/30            (generic: no product or maker)

        Falls back to `name` whenever the parts have not been filled in, so a
        record that predates this structure is unaffected. `source_name` keeps
        the original title either way, so a figure can still be traced back to
        its EPD document.

        The material is omitted when it is only repeating the record's own
        category. For the ~1,580 EPDs whose material_name was derived from that
        category there is nothing new in the prefix, and the picker already
        prints the category as a badge beside the name, so including it gave
        every row a stutter - "Ready mixed concrete - Shotcrete" sitting next to
        a badge reading "Ready mixed concrete". Search is unaffected: it queries
        material_name directly and does not care what is displayed.
        """
        if not self.material_name:
            return self.name
        category_name = self.category.name_en if self.category_id else None
        product = self.product_name or ""
        # Drop the material when the badge beside it already says so, or when
        # the product name contains it - "Mortar - Tiger Mortar General
        # Masonry" and "Fly ash - Dry Fly ash" say it twice otherwise.
        redundant = (self.material_name == category_name
                     or self.material_name.lower() in product.lower())
        parts = [] if redundant else [self.material_name]
        if (product
                and product not in parts
                and self.product_name != self.manufacturer):
            parts.append(self.product_name)
        if self.manufacturer:
            parts.append(self.manufacturer)
        if not parts:
            return self.name
        return " - ".join(parts)

    def get_gwp_impact_sum(self, life_cycle_stage):
        """
        Finds the EPDImpact for GWP + given life_cycle_stage and returns
        Decimal(round(value, 2)) divided by self.declared_amount.
        If `all_impacts` was prefetched, it will use that; otherwise it falls
        back to a database query.

        Nine records carry declared_amount = 0, which made every one of these
        divisions raise DivisionByZero. Most callers write
        `get_gwp_impact_sum(...) or 0`, which cannot help because the exception
        is raised before the `or` is reached, so selecting one of those EPDs in
        the material picker returned a 500. There is no meaningful impact per
        unit when the declared amount is zero, so report nothing and let the
        caller's `or 0` do its job.
        """
        if not self.declared_amount:
            return None

        # 1) Try to use the prefetched list first
        impacts_list = getattr(self, "all_impacts", None)

        if impacts_list is not None:
            for epdimpact in impacts_list:
                # Because you did select_related("impact"), these fields are cached
                if (
                    epdimpact.impact.impact_category == "gwp"
                    and epdimpact.impact.life_cycle_stage == life_cycle_stage
                ):
                    # Round to two decimals, wrap in Decimal, then divide
                    rounded = round(epdimpact.value, 2)
                    return Decimal(rounded) / self.declared_amount

            # If no matching GWP impact was found among the prefetched items:
            return Decimal("0")

        # 2) Prefetch wasn’t used, fall back to a DB lookup
        try:
            db_impact = EPDImpact.objects.get(
                epd=self,
                impact__impact_category="gwp",
                impact__life_cycle_stage=life_cycle_stage,
            )
        except EPDImpact.DoesNotExist:
            return Decimal("0")
        else:
            rounded = round(db_impact.value, 2)
            return Decimal(rounded) / self.declared_amount

    def get_penrt_impact_sum(self, life_cycle_stage):
        """
        Finds the EPDImpact for PENRT + given life_cycle_stage and returns
        Decimal(round(value, 2)) divided by self.declared_amount.
        If `all_impacts` was prefetched, it will use that; otherwise it falls
        back to a database query.

        Guarded against declared_amount = 0 for the same reason as
        get_gwp_impact_sum above; this one additionally divided in its
        not-found branch, so it raised even when no PENRT impact existed.
        """
        if not self.declared_amount:
            return None

        # 1) Try to use the prefetched list first
        impacts_list = getattr(self, "all_impacts", None)

        if impacts_list is not None:
            for epdimpact in impacts_list:
                # Because you did select_related("impact"), these fields are cached
                if (
                    epdimpact.impact.impact_category == "penrt"
                    and epdimpact.impact.life_cycle_stage == life_cycle_stage
                ):
                    # Round to two decimals, wrap in Decimal, then divide
                    rounded = round(epdimpact.value, 2)
                    return Decimal(rounded) / self.declared_amount

            # If no matching GWP impact was found among the prefetched items:
            return Decimal("0") / self.declared_amount

        # 2) Prefetch wasn’t used, fall back to a DB lookup
        try:
            db_impact = EPDImpact.objects.get(
                epd=self,
                impact__impact_category="penrt",
                impact__life_cycle_stage=life_cycle_stage,
            )
        except EPDImpact.DoesNotExist:
            return Decimal("0") / self.declared_amount
        else:
            rounded = round(db_impact.value, 2)
            return Decimal(rounded) / self.declared_amount

    def get_available_units(self):
        units = {self.declared_unit}
        if self.declared_unit not in [Unit.KG, Unit.M3, Unit.KWH]:
            return list(units)
        for item in (self.conversions or []):
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


    def get_epd_info(self, dimension):
        """Takes an assembly dimension"""
        from pages.views.assembly.epd_dimension_info import get_epd_dimension_info
        if dimension and dimension != "None":
            return get_epd_dimension_info(dimension, self.declared_unit)
        else:
            selection_text = []
            selection_units = self.get_available_units()
            return selection_text, selection_units


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
        if self.label.scale_parameters:
            valid_options = list(self.label.scale_parameters)
            if self.score not in valid_options:
                raise ValidationError(
                    f"Label score '{self.score}' needs to be in Scale Parameters: {self.label.scale_parameters}."
                )

    def save(self, *args, **kwargs):
        """
        Override save to include clean validation.
        """
        self.clean()
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.epd.name} - {self.label.name}: {self.score}"