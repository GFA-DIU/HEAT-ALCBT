from django.db import models
from django.utils.translation import gettext_lazy as _

from pages.models.building import Building
from pages.models.building_operation.chilling import RefrigerantGWP, RefrigerantType


class EfficiencyMetric(models.TextChoices):
    """Which efficiency figure the user read off their equipment label.

    Two things separate these, and only one of them is a unit conversion.

    UNITS. Most are dimensionless W/W; one is not:

      COP     W/W, full load
      EER_WW  W/W, full load - Mitsubishi's Indian sheets and Daikin's
              Indonesian cassette sheets publish EER this way
      EER     Btu/h per watt - the Thai EGAT No.5 label, where the No.5
              threshold is >= 11.60. The only one that needs dividing by 3.412
      ISEER   W/W - India's BEE defines it as CSTL/CSEC, both in Wh
      CSPF    W/W - Indonesian and Vietnamese labels
      SEER    W/W here; the rating standard varies by market, so the figure is
              stored as given and not converted

    BASIS. Seasonal and full-load ratings are different quantities even when
    their units agree. ISEER, CSPF and SEER already average over a cooling
    season, so using one as an instantaneous COP overstates efficiency at
    design conditions. Converting units does not turn a seasonal rating into a
    full-load COP, and BEAT does not pretend otherwise - it records the basis.

    EER being W/W on some sheets and Btu/h per W on others is exactly why the
    metric has to be stored rather than inferred. The earlier single "EER"
    choice assumed Btu/h per W for everyone.

    Storing the choice matters as much as converting it: without it, re-opening
    a saved record recomputes the energy against whatever the form defaults to,
    silently changing a number the user never touched.
    """

    COP = "cop", _("COP - full load (W/W)")
    EER_WW = "eer_ww", _("EER - full load (W/W)")
    EER = "eer", _("EER - full load (Btu/h per W)")
    ISEER = "iseer", _("ISEER - seasonal (W/W)")
    CSPF = "cspf", _("CSPF - seasonal (W/W)")
    SEER = "seer", _("SEER - seasonal (W/W)")
    SEER_BTU = "seer_btu", _("SEER - seasonal (Btu/h per W)")


#: Metrics already on the COP basis (W/W). Only plain EER in Btu/h per watt
#: converts, by dividing by 3.412.
DIMENSIONLESS_METRICS = ("cop", "eer_ww", "iseer", "cspf", "seer")

#: Seasonal ratings: an average over a cooling season, not a full-load COP.
#: Kept separate because converting units never turns one into the other.
SEASONAL_METRICS = ("iseer", "cspf", "seer", "seer_btu")


class PackagedACSubType(models.TextChoices):
    """Forms a packaged or ductable unit actually takes.

    Cassette is deliberately absent. A cassette is the ceiling-recessed indoor
    unit of a split system - it blows straight into the room and has no
    ductwork - so it is its own cooling type, not a kind of packaged unit.
    Offering it in both places is what let the same equipment be filed two
    different ways.
    """

    ROOFTOP = "rooftop", _("Rooftop Unit")
    FLOOR_STANDING = "floor_standing", _("Floor-standing")
    DUCTABLE = "ductable", _("Ductable")


class CoolingSystemAirConditioner(models.Model):
    building = models.ForeignKey(
        Building,
        on_delete=models.CASCADE,
        related_name="air_conditioners",
        verbose_name=_("Building"),
    )
    ac_type = models.CharField(
        max_length=50,
        choices=[
            ("window", _("Window Air Conditioners")),
            ("split", _("Split Air Conditioners")),
            ("cassette", _("Cassette / Ceiling-mounted Air Conditioners")),
            ("vrv", _("VRV/VRF (Variable Refrigerant Volume/Flow)")),
            ("packaged", _("Packaged/Ductable Air Conditioners")),
        ],
        verbose_name=_("Air Conditioners Type"),
    )
    packaged_subtype = models.CharField(
        max_length=50,
        choices=PackagedACSubType.choices,
        null=True,
        blank=True,
        verbose_name=_("Packaged AC Sub-type"),
    )
    year_of_installation = models.PositiveIntegerField(
        verbose_name=_("Year of Installation")
    )
    operation_hours_per_workday = models.PositiveSmallIntegerField(
        null=True, blank=True, verbose_name=_("Operation Hours per Workday")
    )
    workdays_per_week = models.PositiveSmallIntegerField(
        null=True, blank=True, verbose_name=_("Workdays per Week")
    )
    workweeks_per_year = models.PositiveSmallIntegerField(
        null=True, blank=True, verbose_name=_("Workweeks per Year")
    )
    refrigerant_type = models.CharField(
        max_length=50,
        choices=RefrigerantType.choices,
        verbose_name=_("Type of Refrigerants"),
    )
    refrigerant_quantity_kg = models.DecimalField(
        max_digits=8, decimal_places=2,
        verbose_name=_("Refrigerant Quantity (Kg)")
    )
    total_cooling_load_rt = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name=_("Total Cooling Load for Split/VRV (RT)")
    )
    cooling_capacity_per_unit_kw = models.DecimalField(
        max_digits=10,
        decimal_places=3,
        null=True,
        blank=True,
        verbose_name=_("Cooling Capacity per Unit (kW)"),
    )
    baseline_efficiency_kw_per_rt = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name=_("Baseline Split Unit/VRV System Efficiency (kW/RT)"),
    )
    eer_iseer_cop = models.DecimalField(
        max_digits=9,
        decimal_places=4,
        null=True,
        blank=True,
        verbose_name=_("EER / ISEER / COP"),
    )
    efficiency_metric = models.CharField(
        max_length=10,
        choices=EfficiencyMetric.choices,
        default=EfficiencyMetric.COP,
        # blank=True so the form falls back to the default instead of demanding
        # the field; a default alone does not make a ModelForm field optional.
        blank=True,
        verbose_name=_("Efficiency metric"),
        help_text=_("Which figure eer_iseer_cop holds. EER is the only one "
                    "that needs converting to a COP."),
    )
    power_input_per_unit_kw = models.DecimalField(
        max_digits=8,
        decimal_places=3,
        null=True,
        blank=True,
        verbose_name=_("Power Input per Unit (kW)"),
    )
    baseline_refrigerant_emission_factor = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name=_("Baseline Refrigerant Emission Factor (GWP)"),
    )
    baseline_leakage_factor_percent = models.PositiveIntegerField(
        default=2, verbose_name=_("Baseline Leakage Factor (%)")
    )
    total_energy_consumption_kwh_per_year = models.DecimalField(
        max_digits=12,
        decimal_places=3,
        null=True,
        blank=True,
        verbose_name=_(
            "Total Energy Consumption of Cooling System Annually (kWh/year)"
        ),
    )
    number_of_units = models.PositiveIntegerField(
        verbose_name=_("Total Number of Split/VRV Units")
    )
    total_system_power_kw = models.PositiveIntegerField(
        null=True, blank=True, verbose_name=_("Total Split Unit/VRV System Power (kW)")
    )
    cop = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True, verbose_name=_("COP")
    )
    iseer_rating = models.DecimalField(
        max_digits=4,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name=_("ISEER Rating"),
    )
    energy_efficiency_label = models.CharField(
        max_length=1,
        null=True,
        blank=True,
        choices=[(c, c) for c in ['A', 'B', 'C', 'D', 'E', 'F', 'G']],
        verbose_name=_("Energy Efficiency Label (A–G)"),
    )
    number_of_stars = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        choices=[(i, _(str(i))) for i in range(1, 6)],
        verbose_name=_("Number of Stars (1–5)"),
    )

    def save(self, *args, **kwargs):
        if self.baseline_refrigerant_emission_factor is None and self.refrigerant_type:
            self.baseline_refrigerant_emission_factor = RefrigerantGWP.get_gwp(self.refrigerant_type)
        super().save(*args, **kwargs)
