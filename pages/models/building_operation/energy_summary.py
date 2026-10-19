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
from pages.models.building_operation.ventilation import (
    VentilationSystem, VentilationType)

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


LIFT_ESTIMATE_FRACTION = Decimal("0.075")


def lift_estimate_kwh(cooling, ventilation, lighting, hot_water):
    """The 7.5% top-down lift estimate. The only implementation.

    It deliberately takes the four modelled systems and NOT the building's
    whole electricity. The lift form's JavaScript used to call /total-kwh/,
    which sums every operational product in kWh including plug and equipment
    loads, so the figure it pre-filled was about 20% higher than the one the
    summary showed for the same building - 69,189.15 against 57,657.6. The
    tooltip, the hint and this model all said four systems; only the
    JavaScript disagreed, and it was the number the user actually saw.

    Accepting that prefill saved it as an entered value, after which the
    estimate stopped applying at all.
    """
    base = sum(
        Decimal(str(v)) for v in (cooling, ventilation, lighting, hot_water)
        if v is not None
    )
    return (base * LIFT_ESTIMATE_FRACTION).quantize(Decimal("0.001"))


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

    # Does this building have plug and equipment loads at all?
    #
    # True  - yes, and plug_load_kwh or plug_load_percent says how much
    # False - no, and the figure is zero and stays zero
    # None  - not stated, so BEAT shows the typical share for the building
    #         type, clearly labelled as an estimate
    #
    # Without this there was no way to say "no plug load" and have it stick:
    # a stored 0 was indistinguishable from an unanswered question, so the row
    # could show a 0 override beside a 20% basis and contradict itself.
    has_plug_load = models.BooleanField(
        null=True, blank=True,
        verbose_name=_("Building has plug and equipment loads"),
    )

    # The percentage of system energy the user says their plug load is.
    #
    # Overwriting the kWh was the only way to correct plug load, which hid
    # where the number came from and went stale the moment a system changed.
    # A percentage stays live: change the lighting and the plug load follows.
    # Blank means BEAT uses the typical share for the building type.
    plug_load_percent = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True,
        verbose_name=_("Plug load as a percentage of system energy"),
        help_text=_(
            "Share of cooling, ventilation, lighting and hot water energy that "
            "plug and equipment loads add. Leave blank to use the typical "
            "share for this building type."
        ),
    )

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

        # Cassette air conditioners are cooling equipment, but the ventilation
        # form offered a "Ceiling/Wall Mounted Cassette AC" type and 106 records
        # across 67 buildings were entered there - it is the most used
        # ventilation type in the database. Their energy is computed exactly as
        # the cooling form computes it (power x hours x days x weeks), so the
        # figures are right; only the category was wrong, which put cooling
        # energy into the ventilation line of every report and benchmark.
        #
        # They are counted as cooling here rather than physically moved,
        # because CoolingSystemAirConditioner requires year_of_installation,
        # refrigerant_type and refrigerant_quantity_kg, none of which the
        # ventilation form collects. Moving the rows would mean inventing three
        # values per record. Building totals are unaffected either way - this
        # only decides which line the energy is reported on.
        cassette_qs = VentilationSystem.objects.filter(
            building=b, ventilation_type=VentilationType.CASSETTE_AC)
        other_vent_qs = VentilationSystem.objects.filter(building=b).exclude(
            ventilation_type=VentilationType.CASSETTE_AC)

        # Cooling: AC units + chillers + cassette ACs filed under ventilation
        ac_qs = CoolingSystemAirConditioner.objects.filter(building=b)
        chiller_qs = CoolingSystemChiller.objects.filter(building=b)
        if ac_qs.exists() or chiller_qs.exists() or cassette_qs.exists():
            ac_sum = ac_qs.aggregate(s=Sum("total_energy_consumption_kwh_per_year"))["s"] or 0
            ch_sum = chiller_qs.aggregate(s=Sum("total_energy_consumption_kwh_per_year"))["s"] or 0
            cas_sum = cassette_qs.aggregate(
                s=Sum("total_energy_consumption_kwh_per_year"))["s"] or 0
            self.cooling_kwh = ac_sum + ch_sum + cas_sum
            self.is_manual_cooling = False
        elif not self.is_manual_cooling:
            self.cooling_kwh = None

        # Ventilation: everything except the cassettes counted above, minus any
        # fan whose parent cooling record already includes it.
        #
        # BEAT used to add every record and deduct nothing, with no link between
        # an indoor unit and the outdoor unit serving it. That made a matched
        # split system's indoor fan countable twice - once inside the cooling
        # figure derived from capacity and COP, once as a fan coil unit - and
        # BEAT could not tell that apart from a chilled-water FCU, where adding
        # both is correct.
        #
        # A fan is now excluded only when the user has BOTH linked it to a
        # cooling record AND said that record's figure covers the complete
        # system. An unlinked fan, or a parent whose boundary is unspecified,
        # is added exactly as before - which is why no existing figure moves.
        if other_vent_qs.exists():
            vent_total = 0
            for v in other_vent_qs.select_related(
                    "cooling_parent_ac", "cooling_parent_chiller"):
                if v.fan_energy_already_counted:
                    continue
                vent_total += v.total_energy_consumption_kwh_per_year or 0
            self.ventilation_kwh = vent_total
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

        # Hot water
        hw_qs = HotWaterSystem.objects.filter(building=b)
        if hw_qs.exists():
            self.hot_water_kwh = hw_qs.aggregate(
                s=Sum("total_energy_consumption_kwh_per_year")
            )["s"] or 0
            self.is_manual_hot_water = False
        elif not self.is_manual_hot_water:
            self.hot_water_kwh = None

        # Lift & Escalator.
        #
        # A figure the user actually entered always wins. Only when every lift
        # record leaves it blank does BEAT fall back to the top-down estimate of
        # 7.5% of the other modelled systems.
        #
        # Blank and zero mean different things here, which is why this checks for
        # None rather than truthiness: blank means "estimate it for me", while an
        # explicit 0 means "there is no lift energy" and is respected. Previously
        # the estimate overwrote the entered value unconditionally, so a building
        # whose other systems were all zero reported 0 kWh with no way to correct
        # it, and the number of lifts appeared to do nothing.
        #
        # Computed AFTER the four systems above so their current values are
        # available. Note the 7.5% method is driven by the other systems, not by
        # how many lifts there are - the lift count is recorded for reference.
        lift_qs = LiftEscalatorSystem.objects.filter(building=b)
        if lift_qs.exists():
            entered = [
                Decimal(str(v)) for v in lift_qs.values_list(
                    "annual_energy_consumption_kwh", flat=True
                ) if v is not None
            ]
            lift_count = sum(
                int(n or 0) for n in lift_qs.values_list("number_of_lifts", flat=True)
            )
            if entered:
                self.lift_escalator_kwh = sum(entered).quantize(Decimal("0.001"))
            elif lift_count <= 0:
                # A building with no lifts uses no lift energy.
                #
                # The estimate used to fire on the existence of a record, not
                # on whether it described any lifts, so a card saying
                # "number of lifts: 0" still produced 65,943 kWh a year out of
                # 7.5% of the other systems. The count is the whole point of
                # the question.
                self.lift_escalator_kwh = Decimal("0.000")
            else:
                self.lift_escalator_kwh = lift_estimate_kwh(
                    self.cooling_kwh, self.ventilation_kwh,
                    self.lighting_kwh, self.hot_water_kwh,
                )
            self.is_manual_lift_escalator = False
        elif not self.is_manual_lift_escalator:
            self.lift_escalator_kwh = None

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

    @property
    def lift_energy_is_estimated(self):
        """True when the lift figure is BEAT's 7.5%, not a figure from a meter.

        It is an estimate only when there are lift records, none of them gives
        an energy figure, and nothing was typed into the summary by hand.
        """
        if self.is_manual_lift_escalator:
            return False
        qs = LiftEscalatorSystem.objects.filter(building=self.building)
        if not qs.exists():
            return False
        return not any(
            v is not None for v in
            qs.values_list("annual_energy_consumption_kwh", flat=True)
        )

    @property
    def plug_load_base(self):
        """The systems a plug-load percentage is taken of.

        Always the four measured systems; lift joins them only when its figure
        is real. When no lift energy was entered, the lift number is itself
        7.5% of these same four systems, so counting it would take a
        percentage of a percentage and inflate plug load off the back of an
        estimate rather than a measurement.

        A metered or hand-entered lift figure is a measurement like any other
        and belongs in the base. The energy-mismatch check is unaffected and
        still uses systems_sum, where counting every system is correct.
        """
        vals = [self.cooling_kwh, self.ventilation_kwh,
                self.lighting_kwh, self.hot_water_kwh]
        if not self.lift_energy_is_estimated:
            vals.append(self.lift_escalator_kwh)
        nums = [Decimal(str(v)) for v in vals if v is not None]
        return sum(nums) if nums else Decimal("0")

    @property
    def plug_load_effective(self):
        """The plug-load figure actually used, whatever its basis.

        total_kwh already resolves this - entered figure first, else the
        estimate - and the row must show the same number the total adds, or
        the panel does not add up on screen.
        """
        if self.has_plug_load is False:
            return Decimal("0")
        if self.plug_load_kwh is not None:
            return Decimal(str(self.plug_load_kwh))
        return self.suggested_plug_load()

    @property
    def plug_load_basis(self):
        """Which of the three answers the plug-load figure rests on.

        Exactly one, so the row can never show a percentage beside a figure
        that contradicts it. "none" means the building was said to have no
        plug load; "metered" and "percent" are the two ways of saying how
        much; "estimated" is BEAT's typical share while the question is
        unanswered.
        """
        if self.has_plug_load is False:
            return "none"
        if self.plug_load_kwh is not None:
            return "metered"
        if self.plug_load_percent is not None:
            return "percent"
        if self.total_override_kwh is not None:
            return "difference"
        return "estimated"

    @property
    def plug_load_default_percent(self):
        """The typical share for this building type, shown when none is set."""
        building = self.building
        type_name = (
            building.category.category.name
            if building and building.category and building.category.category
            else ""
        )
        return plug_load_factor_for(type_name) * Decimal("100")

    def suggested_plug_load(self):
        """Estimate plug load when the user hasn't entered one.

        - If a metered bill total is present: plug = bill − Σ(all systems).
        - Else, if a percentage was entered: plug = base × that percentage.
        - Else, if systems are present: plug = base × building-type factor.
        - Else (no bill, no systems): None (nothing to base an estimate on).

        The difference method uses every system, because it is reconciling
        against a bill that covers them all. The percentage methods use
        plug_load_base.
        """
        # An explicit "no" is an answer, not a blank.
        if self.has_plug_load is False:
            return Decimal("0")
        if self.total_override_kwh is not None and self.systems_sum > 0:
            return max(Decimal("0"),
                       Decimal(str(self.total_override_kwh)) - self.systems_sum)
        systems = self.plug_load_base
        if systems > 0 and self.plug_load_percent is not None:
            return (systems * Decimal(str(self.plug_load_percent))
                    / Decimal("100")).quantize(Decimal("0.001"))
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
        """Annual building energy, including an estimated plug load.

        A metered/bill total is authoritative and already includes plug loads.

        Otherwise the plug load counts whether the user typed it or BEAT
        estimated it. The screen shows the estimate on its own row labelled
        "ESTIMATED", and previously the total quietly left it out - so a summary
        reading 8 + 0.6 + 2.15 totalled 8.6, which looks like an arithmetic
        error rather than a deliberate exclusion.
        """
        if self.total_override_kwh is not None:
            return Decimal(str(self.total_override_kwh))
        plug = self.plug_load_kwh
        if plug is None:
            plug = self.suggested_plug_load()
        vals = [
            self.cooling_kwh,
            self.ventilation_kwh,
            self.lighting_kwh,
            self.lift_escalator_kwh,
            self.hot_water_kwh,
            plug,
        ]
        nums = [Decimal(str(v)) for v in vals if v is not None]
        return sum(nums) if nums else None

    @property
    def plug_load_is_estimated(self):
        """True when the plug load in total_kwh came from the estimate."""
        return (self.total_override_kwh is None
                and self.plug_load_kwh is None
                and self.suggested_plug_load() is not None)

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
