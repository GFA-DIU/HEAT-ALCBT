"""Layer 2 - what replacing a building's equipment with efficient units saves.

Layer 3 (``building_stats.get_operational_savings_measures``) asks what a
control bolted onto the existing equipment saves: a VSD, a sensor, a BMS. This
layer asks the other question - what if the equipment itself were replaced -
and the two are not the same saving. A chiller with a VSD fitted is still the
same chiller.

Each record is compared against the benchmark for its own type and country in
``system_efficiency_data``, and the per-system fraction is **weighted by each
record's own annual energy**, not averaged across records. A building with one
efficient 500 kWh unit and one poor 50,000 kWh unit is not half-way efficient.

Records with no efficiency, no energy, or no published benchmark are counted
and reported, never estimated. The counts are what tell a user whether a small
saving means "little to gain" or "we could only look at two of your nine
units".
"""
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List

from pages.forms.cooling_system_form import (
    AC_EFFICIENCY_RANGES, EFFICIENCY_RANGES as CHILLER_EFFICIENCY_RANGES,
)
from pages.views.building.system_efficiency_data import (
    HIGHER_IS_BETTER, LPD_BENCHMARKS, LOWER_IS_BETTER, benchmark_source,
    cop_to_kw_per_rt,
    efficiency_saving_fraction, resolve_system_benchmark,
)

# Specific fan power the ventilation form tells users to expect: its tooltip
# reads "typical range 0.30 to 1.20 W/CMH". test_equipment_savings.py fails if
# that wording changes, so the guard and the on-screen advice cannot drift.
SFP_PLAUSIBLE = (Decimal("0.30"), Decimal("1.20"))

# A boiler cannot exceed 1.0 and a heat pump cannot have a COP below 1 - these
# are physical limits, not chosen thresholds.
FRACTION_PLAUSIBLE = (Decimal("0.01"), Decimal("1.00"))
COP_PLAUSIBLE = (Decimal("1.00"), Decimal("10.00"))


def _within(value, bounds, direction=LOWER_IS_BETTER):
    """True when a stored figure is usable as a benchmark input.

    The guard is **directional**, and only one end of the range matters.

    A false saving comes from an implausibly *bad* stored value: 60 W/CMH
    against a 0.25 benchmark reads as a 99.6% saving, which is large, specific
    and wrong. An implausibly *good* value cannot do that - it is already past
    the target, so efficiency_saving_fraction returns zero on its own.

    Guarding both ends therefore buys nothing and costs real equipment. A
    5-star Indian split at ISEER 5.3 is 0.66 kW/RT, below the 0.75 the cooling
    form calls typical for a split, and rejecting it would mean refusing to
    benchmark the best units in the database.

    The bounds themselves are BEAT's own: EFFICIENCY_RANGES and
    AC_EFFICIENCY_RANGES from the cooling form, and the 0.30 to 1.20 W/CMH the
    ventilation form prints in its tooltip. Nothing new is invented here, and
    if those ever change the benchmarks follow.

    The data this protects against is concentrated exactly where last week's
    ventilation work predicted: of 106 cassette rows only 12 carry a plausible
    specific fan power, against 43 of 46 AHU rows. The field was required and
    unread on the cassette form, so people typed whatever cleared the
    validator.
    """
    if value is None:
        return False
    low, high = bounds
    if direction == LOWER_IS_BETTER:
        return value <= high      # too high is a data error; too low is good equipment
    return value >= low           # too low is a data error; too high is good equipment

# BEAT ac_type -> 1_System_Efficiency row.
#
# `window` and `packaged` are deliberately absent: the workbook publishes no
# row for either, and borrowing the split figure for a window unit would be
# inventing a benchmark. 20 window units in the database report nothing.
AC_TYPE_TO_BENCHMARK = {
    "split": "split",
    "cassette": "split",      # a cassette is a split with a different indoor unit
    "vrv": "vrv",
}

CHILLER_TYPE_TO_BENCHMARK = {
    "air_cooled": "air_cooled_chiller",
    "water_cooled": "water_cooled_chiller",
}

HOT_WATER_TYPE_TO_BENCHMARK = {
    "heat-pump": "hot_water_heat_pump",
    "boiler": "boiler",
    "solar": "solar_water_heater",
}

# EPI building type -> 3_LPD_Benchmarks row.
#
# The category itself is resolved by _resolve_epi_type in
# operational_benchmark_data, which Layer 1 already uses and which was verified
# against the seeded taxonomies in the v1.1 spec. Writing a second matcher here
# would give the same building two different types the first time either
# taxonomy changed.
#
# Both vocabularies come from the same workbook, so only two words differ:
# "Shopping Mall" is "Retail" on the LPD sheet, and "Institute" is "School".
EPI_TYPE_TO_LPD = {
    "Office": "Office",
    "Shopping Mall": "Retail",
    "Hospital": "Hospital",
    "Hotel": "Hotel",
    "Institute": "School",
    "Residential": "Residential",
}


def _dec(value):
    try:
        return Decimal(str(value))
    except (TypeError, ValueError, InvalidOperation):
        return None


def _country_name(building) -> str:
    country = getattr(building, "country", None)
    return getattr(country, "name", "") or ""


def _lpd_type(building):
    """Resolve the building's category to an LPD row, or None.

    Defers to Layer 1's resolver so a building cannot be an Office for its EPI
    benchmark and a Hotel for its lighting one.
    """
    from pages.views.building.operational_benchmark_data import _resolve_epi_type
    resolved = _resolve_epi_type(building)
    if not resolved:
        return None
    return EPI_TYPE_TO_LPD.get(resolved[0])


def _lpd_target(lpd_type, country):
    """Best published LPD for a type and country, W/m2, lower is better.

    India publishes three tiers; Super ECBC is the best practice and is used
    where it exists. Everyone else publishes one national figure, and LEED is
    offered alongside it.
    """
    row = LPD_BENCHMARKS.get(lpd_type)
    if not row:
        return None, None
    if country == "India":
        for key, basis in (("India_Super_ECBC", "Super ECBC"),
                           ("India_ECBC+", "ECBC+"),
                           ("India", "ECBC")):
            if row.get(key) is not None:
                return row[key], basis
        return None, None
    national = row.get(country)
    leed = row.get("leed")
    if national is None and leed is None:
        return None, None
    if national is None:
        return leed, "LEED"
    if leed is not None and leed < national:
        return leed, "LEED"
    return national, "national baseline"


def _blank_system(key, label, unit):
    return {
        "key": key, "label": label, "unit": unit,
        "records": 0, "benchmarked": 0, "already_better": 0, "no_benchmark": 0,
        "energy_kwh": 0.0, "benchmarked_energy_kwh": 0.0,
        "saving_kwh": 0.0, "saving_fraction": 0.0,
        "target": None, "target_basis": None, "current_weighted": None,
        # Where the target came from, and whether anyone checked it. The chart
        # draws a system with no benchmark at full height and hatched: its
        # energy is real, and "not assessed" must not look like "nothing to
        # gain here".
        "source": None, "verified": False, "has_benchmark": False,
    }


def _accumulate(system, current, target, direction, energy, basis, unit,
                source=None, verified=False):
    """Fold one record into a system's running totals."""
    system["records"] += 1
    energy = float(energy or 0.0)
    system["energy_kwh"] += energy
    if target is not None:
        # Record the target as soon as it is known, not after the record has
        # been found usable. A system whose benchmark exists but whose records
        # all carry unusable figures - ventilation, where most stored specific
        # fan powers are outside the range the form itself declares - would
        # otherwise report "Target None", claiming to have a benchmark it had
        # just thrown away.
        system["has_benchmark"] = True
        system["source"] = source
        system["verified"] = verified
        system["target"] = target
        system["target_basis"] = basis
        system["unit"] = unit
    if current is None or target is None:
        system["no_benchmark"] += 1
        return
    fraction = efficiency_saving_fraction(current, target, direction)
    system["benchmarked_energy_kwh"] += energy
    if fraction <= 0:
        system["already_better"] += 1
        return
    system["benchmarked"] += 1
    system["saving_kwh"] += energy * fraction


def _finalise(system):
    """Energy-weighted fraction over the records that could be benchmarked."""
    base = system["benchmarked_energy_kwh"]
    system["saving_fraction"] = round(system["saving_kwh"] / base, 4) if base else 0.0
    system["saving_kwh"] = round(system["saving_kwh"], 1)
    system["energy_kwh"] = round(system["energy_kwh"], 1)
    system["benchmarked_energy_kwh"] = round(system["benchmarked_energy_kwh"], 1)
    return system


def get_equipment_efficiency_savings(building) -> Dict[str, Any]:
    """Layer 2 for one building. Energy only - carbon is applied by the caller.

    Returns ``{systems: [...], total_saving_kwh, coverage, country}``. Every
    figure is annual kWh; nothing here knows the grid factor.
    """
    country = _country_name(building)

    cooling = _blank_system("cooling", "Cooling", "kW/RT")
    ventilation = _blank_system("ventilation", "Ventilation", "W/CMH")
    hot_water = _blank_system("hot_water", "Hot water", "COP")
    lighting = _blank_system("lighting", "Lighting", "W/m2")

    # --- cooling: air conditioners, whose efficiency is a COP-family figure
    for ac in building.air_conditioners.all():
        key = AC_TYPE_TO_BENCHMARK.get(ac.ac_type)
        energy = ac.total_energy_consumption_kwh_per_year
        bench = resolve_system_benchmark(key, country) if key else None
        current = None
        if bench is not None:
            # Every stored metric in the database is `cop`. The others added
            # for Thai, Indonesian and Vietnamese labels are dimensionless
            # W/W too, except EER and SEER in Btu/h per watt, which the
            # cooling form already converts before storing.
            current = cop_to_kw_per_rt(ac.eer_iseer_cop)
            if not _within(current, AC_EFFICIENCY_RANGES.get(
                    ac.ac_type, (Decimal("0.4"), Decimal("2.5")))):
                current = None
        _accumulate(cooling, float(current) if current else None,
                    bench["target"] if bench else None,
                    LOWER_IS_BETTER, energy,
                    bench["target_basis"] if bench else None, "kW/RT",
                    bench["source"] if bench else None,
                    bench["verified"] if bench else False)

    # --- cooling: chillers, already stated in kW/RT
    for ch in building.chillers.all():
        key = CHILLER_TYPE_TO_BENCHMARK.get(ch.chiller_type)
        bench = resolve_system_benchmark(key, country) if key else None
        current = _dec(ch.baseline_cooling_efficiency_kw_h)
        if not _within(current, CHILLER_EFFICIENCY_RANGES.get(
                ch.chiller_type, (Decimal("0.4"), Decimal("1.5")))):
            current = None
        _accumulate(cooling, float(current) if current else None,
                    bench["target"] if bench else None,
                    LOWER_IS_BETTER, ch.total_energy_consumption_kwh_per_year,
                    bench["target_basis"] if bench else None, "kW/RT",
                    bench["source"] if bench else None,
                    bench["verified"] if bench else False)

    # --- ventilation: specific fan power, already in the benchmark's unit
    #
    # Only AHU and DOAS derive their energy from this figure. On the FCU,
    # cassette and fan forms it is optional and reference-only, so most rows
    # carry nothing to compare and land in no_benchmark.
    bench_vent = resolve_system_benchmark("ventilation", country)
    for v in building.ventilation_systems.all():
        current = _dec(v.baseline_efficiency_w_cmh)
        if not _within(current, SFP_PLAUSIBLE):
            current = None
        _accumulate(ventilation, float(current) if current else None,
                    bench_vent["target"] if bench_vent else None,
                    LOWER_IS_BETTER, v.total_energy_consumption_kwh_per_year,
                    bench_vent["target_basis"] if bench_vent else None, "W/CMH",
                    bench_vent["source"] if bench_vent else None,
                    bench_vent["verified"] if bench_vent else False)

    # --- hot water: COP for a heat pump, a fraction for boiler and solar
    for h in building.hot_water_systems.all():
        key = HOT_WATER_TYPE_TO_BENCHMARK.get(h.type_of_hot_water_system)
        bench = resolve_system_benchmark(key, country) if key else None
        current = _dec(h.baseline_efficiency)
        bounds = COP_PLAUSIBLE if key == "hot_water_heat_pump" else FRACTION_PLAUSIBLE
        # Hot water is higher-is-better, so the low end is the data-error end.
        # A boiler efficiency above 1.0 is impossible, so it is capped too.
        if not _within(current, bounds, HIGHER_IS_BETTER) or (
                key != "hot_water_heat_pump" and current and current > 1):
            current = None
        _accumulate(hot_water, float(current) if current else None,
                    bench["target"] if bench else None,
                    bench["direction"] if bench else LOWER_IS_BETTER,
                    h.total_energy_consumption_kwh_per_year,
                    bench["target_basis"] if bench else None,
                    bench["unit"] if bench else "COP",
                    bench["source"] if bench else None,
                    bench["verified"] if bench else False)

    # --- lighting: power density, W/m2, derived per room
    lpd_type = _lpd_type(building)
    lpd_target, lpd_basis = _lpd_target(lpd_type, country) if lpd_type else (None, None)
    lpd_source, lpd_status = benchmark_source("lighting", country)
    for l in building.lighting_systems.all():
        # Derived from installed power and room area, NOT from
        # baseline_lighting_power_density.
        #
        # That column is named as though it holds W/m2 and does not: all 491
        # rows in production sit between 0.00 and 2.00 with a median of 0.00,
        # against a real lighting power density of 5 to 16 W/m2. Trusting it
        # made every building "already better than best practice" on the
        # strength of a lighting load of zero.
        #
        # power x 1000 / area gives a median of 3.33 W/m2 over the same rows,
        # which is a plausible figure for LED-lit space. The column itself is
        # left alone: what it actually holds is a separate question, recorded
        # in docs/AGENT_HANDOVER.md.
        current = None
        power_kw = _dec(l.total_lighting_power_kw)
        area = _dec(l.area_of_room)
        if power_kw and area and area > 0:
            current = power_kw * Decimal("1000") / area
        _accumulate(lighting, float(current) if current else None,
                    lpd_target, LOWER_IS_BETTER,
                    l.total_energy_consumption_kwh_per_year,
                    lpd_basis, "W/m2", lpd_source, lpd_status == "verified")

    systems: List[Dict[str, Any]] = [
        _finalise(s) for s in (cooling, ventilation, hot_water, lighting)
    ]
    present = [s for s in systems if s["records"]]

    return {
        "country": country,
        "lpd_type": lpd_type,
        "systems": present,
        "total_saving_kwh": round(sum(s["saving_kwh"] for s in present), 1),
        "total_energy_kwh": round(sum(s["energy_kwh"] for s in present), 1),
        "coverage": {
            "records": sum(s["records"] for s in present),
            "with_saving": sum(s["benchmarked"] for s in present),
            "already_better": sum(s["already_better"] for s in present),
            "no_benchmark": sum(s["no_benchmark"] for s in present),
        },
    }
