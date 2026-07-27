from decimal import Decimal

from django.db import models
from django.db.models import Sum
from django.utils.translation import gettext_lazy as _

from pages.models.building import Building
from pages.models.building_operation.air_conditioning import CoolingSystemAirConditioner
from pages.models.building_operation.chilling import CoolingSystemChiller
from pages.models.building_operation.general_systems import LiftEscalatorSystem
from pages.models.building_operation.hot_water import HotWaterSystem
from pages.models.building_operation.lighting import LightingSystem
from pages.models.building_operation.ventilation import VentilationSystem

# Plug / equipment load as a fraction of the modelled system energy, used to
# estimate plug load when there is no metered bill total to derive it by
# difference. Keyed by substrings of the building-type name; literature-based
# typical shares of regulated (systems) energy.
_PLUG_LOAD_FACTORS = [
    # Order matters: more specific building types first. Keys are matched as
    # substrings, so avoid short fragments that appear inside other words.
    (("hotel", "hospitality", "resort"), Decimal("0.20")),
    (("retail", "shop", "shopping", "store", "market"), Decimal("0.15")),
    (("home", "resid", "apartment", "dwelling", "housing"), Decimal("0.20")),
    (("office", "business", "commercial", "data centre", "data center"), Decimal("0.25")),
]
_PLUG_LOAD_FACTOR_DEFAULT = Decimal("0.20")


def plug_load_factor_for(type_name):
    """Typical plug-load fraction of system energy for a building type."""
    name = (type_name or "").lower()
    for keys, factor in _PLUG_LOAD_FACTORS:
        if any(k in name for k in keys):
            return factor
    return _PLUG_LOAD_FACTOR_DEFAULT


class EnergySummary(models.Model):
    """
    Stores per-category annual energy consumption for a building.

    Each category field holds either:
    - The auto-calculated sum of all saved system records (when components exist)
    - A manually entered value (when no components exist for that category)

    The is_manual_<category> flags track whether the value was user-entered
    (True) or computed from system records (False). When components exist the
    flag is always False and the value is read-only on the frontend.
    """
    building = models.OneToOneField(
        Building,
        on_delete=models.CASCADE,
        related_name="energy_summary",
        verbose_name=_("Building"),
    )

    cooling_kwh = models.DecimalField(
        max_digits=14, decimal_places=3, null=True, blank=True,
        verbose_name=_("Cooling System (kWh/yr)"),
    )
    is_manual_cooling = models.BooleanField(default=False)

    ventilation_kwh = models.DecimalField(
        max_digits=14, decimal_places=3, null=True, blank=True,
        verbose_name=_("Ventilation System (kWh/yr)"),
    )
    is_manual_ventilation = models.BooleanField(default=False)

    lighting_kwh = models.DecimalField(
        max_digits=14, decimal_places=3, null=True, blank=True,
        verbose_name=_("Lighting System (kWh/yr)"),
    )
    is_manual_lighting = models.BooleanField(default=False)

    lift_escalator_kwh = models.DecimalField(
        max_digits=14, decimal_places=3, null=True, blank=True,
        verbose_name=_("Lift & Escalator System (kWh/yr)"),
    )
    is_manual_lift_escalator = models.BooleanField(default=False)

    hot_water_kwh = models.DecimalField(
        max_digits=14, decimal_places=3, null=True, blank=True,
        verbose_name=_("Hot Water System (kWh/yr)"),
    )
    is_manual_hot_water = models.BooleanField(default=False)

    # Plug / equipment loads (small power, appliances, IT). There is no equipment
    # table to derive these from, so this category is always manually entered.
    plug_load_kwh = models.DecimalField(
        max_digits=14, decimal_places=3, null=True, blank=True,
        verbose_name=_("Plug & Equipment Loads (kWh/yr)"),
    )
    is_manual_plug_load = models.BooleanField(default=True)

    total_override_kwh = models.DecimalField(
        max_digits=14, decimal_places=3, null=True, blank=True,
        verbose_name=_("Total Annual Energy Consumption Override (kWh/yr)"),
    )

    class Meta:
        verbose_name = _("Energy Consumption Summary")
        verbose_name_plural = _("Energy Consumption Summaries")

    def recalculate(self):
        """
        Recompute each category from its system records.
        If a category has system records the value is set to their sum and
        is_manual is forced False.  If a category has no system records the
        existing value (manual or null) is left untouched.
        """
        b = self.building
        had_any_before = self.any_components

        # Cooling: AC units + chillers
        ac_qs = CoolingSystemAirConditioner.objects.filter(building=b)
        chiller_qs = CoolingSystemChiller.objects.filter(building=b)
        if ac_qs.exists() or chiller_qs.exists():
            ac_sum = ac_qs.aggregate(s=Sum("total_energy_consumption_kwh_per_year"))["s"] or 0
            ch_sum = chiller_qs.aggregate(s=Sum("total_energy_consumption_kwh_per_year"))["s"] or 0
            self.cooling_kwh = ac_sum + ch_sum
            self.is_manual_cooling = False
        elif not self.is_manual_cooling:
            self.cooling_kwh = None

        # Ventilation
        vent_qs = VentilationSystem.objects.filter(building=b)
        if vent_qs.exists():
            self.ventilation_kwh = vent_qs.aggregate(
                s=Sum("total_energy_consumption_kwh_per_year")
            )["s"] or 0
            self.is_manual_ventilation = False
        elif not self.is_manual_ventilation:
            self.ventilation_kwh = None

        # Lighting
        light_qs = LightingSystem.objects.filter(building=b)
        if light_qs.exists():
            self.lighting_kwh = light_qs.aggregate(
                s=Sum("total_energy_consumption_kwh_per_year")
            )["s"] or 0
            self.is_manual_lighting = False
        elif not self.is_manual_lighting:
            self.lighting_kwh = None

        # Lift & Escalator
        lift_qs = LiftEscalatorSystem.objects.filter(building=b)
        if lift_qs.exists():
            self.lift_escalator_kwh = lift_qs.aggregate(
                s=Sum("annual_energy_consumption_kwh")
            )["s"] or 0
            self.is_manual_lift_escalator = False
        elif not self.is_manual_lift_escalator:
            self.lift_escalator_kwh = None

        # Hot water
        hw_qs = HotWaterSystem.objects.filter(building=b)
        if hw_qs.exists():
            self.hot_water_kwh = hw_qs.aggregate(
                s=Sum("total_energy_consumption_kwh_per_year")
            )["s"] or 0
            self.is_manual_hot_water = False
        elif not self.is_manual_hot_water:
            self.hot_water_kwh = None

        # NB: a metered/bill total (total_override_kwh) is intentionally kept even
        # when system records exist — it is the authoritative bill figure and lets
        # plug/other loads be derived by difference (bill − Σ systems).

    @property
    def systems_sum(self):
        """Sum of the five modelled systems (excludes plug loads)."""
        vals = [
            self.cooling_kwh,
            self.ventilation_kwh,
            self.lighting_kwh,
            self.lift_escalator_kwh,
            self.hot_water_kwh,
        ]
        nums = [Decimal(str(v)) for v in vals if v is not None]
        return sum(nums) if nums else Decimal("0")

    def suggested_plug_load(self):
        """Estimate plug load when the user hasn't entered one.

        - If a metered bill total is present: plug = bill − Σ(systems) (difference).
        - Else, if systems are present: plug = Σ(systems) × building-type factor.
        - Else (no bill, no systems): None (nothing to base an estimate on).
        """
        systems = self.systems_sum
        if self.total_override_kwh is not None and systems > 0:
            return max(Decimal("0"), Decimal(str(self.total_override_kwh)) - systems)
        if systems > 0:
            building = self.building
            type_name = (
                building.category.category.name
                if building.category and building.category.category
                else ""
            )
            return (systems * plug_load_factor_for(type_name)).quantize(Decimal("0.001"))
        return None

    @property
    def total_kwh(self):
        # A metered/bill total is authoritative and already includes plug loads.
        if self.total_override_kwh is not None:
            return Decimal(str(self.total_override_kwh))
        vals = [
            self.cooling_kwh,
            self.ventilation_kwh,
            self.lighting_kwh,
            self.lift_escalator_kwh,
            self.hot_water_kwh,
            self.plug_load_kwh,
        ]
        nums = [Decimal(str(v)) for v in vals if v is not None]
        return sum(nums) if nums else None

    @property
    def any_components(self):
        """True if any category has system-derived (non-manual) data."""
        return any([
            not self.is_manual_cooling and self.cooling_kwh is not None,
            not self.is_manual_ventilation and self.ventilation_kwh is not None,
            not self.is_manual_lighting and self.lighting_kwh is not None,
            not self.is_manual_lift_escalator and self.lift_escalator_kwh is not None,
            not self.is_manual_hot_water and self.hot_water_kwh is not None,
        ])
