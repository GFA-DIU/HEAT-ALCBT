"""Layer 2 - equipment-efficiency replacement benchmarks.

The question this layer answers: *how much would the building save by replacing
its equipment with efficient units*, as opposed to Layer 3, which asks how much
a control measure bolted onto the existing equipment would save.

Source: ``Operational_Carbon_Benchmark_restructured.xlsx``, sheets
``1_System_Efficiency`` and ``3_LPD_Benchmarks``, the same workbook behind the
Layer 1 EPI benchmarks. Specified in
``docs/Operational_Carbon_Savings_Methodology_and_Logic_v1.1.docx`` section 1,
where Layer 2 was deferred from v1.

Two conventions carried over from the workbook's own ``0_README``:

* **Blank means no benchmark was published. It is never synthesised.** A gap
  here produces "no benchmark for this combination", not an interpolation.
* Savings fractions are decimals (0.20 = 20%).

A third convention is ours, and it exists because of a defect in the source
data - see ``_best_practice_is_credible``.
"""
from decimal import Decimal
from typing import Optional

# 1 refrigeration ton of cooling, in kW.
#
# pages/forms/cooling_system_form.py carries the same constant for its unit
# picker. test_system_efficiency.py asserts the two still agree, because a
# building entered in tons and benchmarked here must not be converted by two
# slightly different numbers.
KW_PER_REFRIGERATION_TON = Decimal("3.516")


# --------------------------------------------------------------------------
# 1_System_Efficiency - baseline efficiency per system per country
# --------------------------------------------------------------------------
# Verbatim from the workbook, including the two values flagged below. Nothing
# is corrected here: the workbook is the source of truth, and a value we think
# is wrong is handled by refusing to use it, not by quietly replacing it.
#
# `lower_is_better` is the workbook's own note: "Lower kW/RT = more efficient".
# For COP and the two fraction rows, higher is better.

LOWER_IS_BETTER = "lower"
HIGHER_IS_BETTER = "higher"

SYSTEM_EFFICIENCY = {
    "air_cooled_chiller": {
        "label": "Air-cooled chiller",
        "unit": "kW/RT",
        "direction": LOWER_IS_BETTER,
        "national": {"India": 1.05, "Indonesia": 1.18, "Vietnam": 1.13,
                     "Thailand": 1.12, "Cambodia": 1.18},
        "leed": 0.94, "edge": 0.85,
    },
    "water_cooled_chiller": {
        "label": "Water-cooled chiller",
        "unit": "kW/RT",
        "direction": LOWER_IS_BETTER,
        "national": {"India": 0.54, "Indonesia": 0.61, "Vietnam": 0.58,
                     "Thailand": 0.61, "Cambodia": 0.61},
        "leed": 0.55, "edge": 0.55,
    },
    "split": {
        "label": "Split unit",
        "unit": "kW/RT",
        "direction": LOWER_IS_BETTER,
        # Vietnam 1.35 is 60% worse than every neighbour (India 0.85,
        # Thailand 0.80, Indonesia and Cambodia 0.84) and sits one cell from
        # the LEED 1.36 below. Both are suspected copy errors; neither is
        # altered here, and _best_practice_is_credible stops LEED being used.
        "national": {"India": 0.85, "Indonesia": 0.84, "Vietnam": 1.35,
                     "Thailand": 0.80, "Cambodia": 0.84},
        "leed": 1.36, "edge": 0.86,
    },
    "vrv": {
        "label": "VRV / VRF system",
        "unit": "kW/RT",
        "direction": LOWER_IS_BETTER,
        # Thailand and LEED are blank in the workbook. Blank is not zero and
        # not interpolated: those combinations report no benchmark.
        "national": {"India": 0.86, "Indonesia": 0.92, "Vietnam": 0.91,
                     "Cambodia": 0.92},
        "leed": None, "edge": 0.74,
    },
    "ventilation": {
        "label": "Ventilation system",
        "unit": "W/CMH",
        "direction": LOWER_IS_BETTER,
        "national": {"India": 0.42, "Indonesia": 0.42, "Vietnam": 0.42,
                     "Thailand": 0.31, "Cambodia": 0.42},
        "leed": 0.31, "edge": 0.25,
    },
    "hot_water_heat_pump": {
        "label": "Hot water (heat pump)",
        "unit": "COP",
        "direction": HIGHER_IS_BETTER,
        "national": {"India": 3.5, "Vietnam": 3.0, "Thailand": 3.5,
                     "Cambodia": 3.5},
        "leed": 3.3, "edge": 3.0,
    },
    "solar_water_heater": {
        "label": "Solar water heater",
        "unit": "fraction",
        "direction": HIGHER_IS_BETTER,
        "national": {"India": 0.65, "Vietnam": 0.60, "Thailand": 0.65,
                     "Cambodia": 0.65},
        "leed": None, "edge": 0.60,
    },
    "boiler": {
        "label": "Boiler",
        "unit": "fraction",
        "direction": HIGHER_IS_BETTER,
        "national": {"India": 0.85, "Vietnam": 0.80, "Thailand": 0.85,
                     "Cambodia": 0.85},
        "leed": 0.80, "edge": 0.89,
    },
}


# --------------------------------------------------------------------------
# 3_LPD_Benchmarks - lighting power density, W/m2
# --------------------------------------------------------------------------
# Lower is always better. India publishes three tiers; the others publish one.
# EDGE is performance-based (">= 65 lumens per watt"), not a density, so it has
# no column here - a luminous efficacy cannot be compared against a W/m2 value.
# India corrected against the code itself, 19.10.2026.
#
# ECSBC 2024 Tables 7.1, 7.2 and 7.3 (Interior Lighting Power, Building Area
# Method), from ESCBC_Commercial.pdf pages 77-78. The workbook's base column
# was right and its ECBC+ and Super columns were shifted one row down the
# table: Shopping Mall had taken Hospital's figures, Hospital had taken
# Hotel's, and Hotel had taken Shopping Mall's.
#
# Hotel is the row that gives it away - the workbook has ECBC+ at 11.3 against
# a base of 9.5, a stricter tier laxer than the one it tightens. The effect on
# Layer 2 was a hotel target 46% too lax and a retail target 29% too strict.
#
#   type            ECSBC   ECSBC+   Super ECSBC
#   Office            9.5      7.6        5.0
#   Hospitals         9.7      7.8        4.9
#   Hotels            9.5      7.6        4.8
#   Shopping Mall    14.1     11.3        7.0
#   Univ. & Schools  11.2      9.0        6.0
LPD_BENCHMARKS = {
    "Office":     {"India": 9.5,  "India_ECBC+": 7.6,  "India_Super_ECBC": 5.0,
                   "Indonesia": 7.53, "Vietnam": 11, "Thailand": 10,
                   "Cambodia": 7.53, "leed": 6.7},
    "Retail":     {"India": 14.1, "India_ECBC+": 11.3, "India_Super_ECBC": 7.0,
                   "Indonesia": 10.76, "Vietnam": 16, "Thailand": 11,
                   "Cambodia": 10.76, "leed": 8.4},
    "Hospital":   {"India": 9.7,  "India_ECBC+": 7.8,  "India_Super_ECBC": 4.9,
                   "Indonesia": 10.33, "Vietnam": 13, "Thailand": 12,
                   "Cambodia": 10.33, "leed": 9.9},
    "Hotel":      {"India": 9.5,  "India_ECBC+": 7.6,  "India_Super_ECBC": 4.8,
                   "Indonesia": 9.04, "Vietnam": 11, "Thailand": 12,
                   "Cambodia": 9.04, "leed": 5.7},
    "School":     {"India": 11.2, "India_ECBC+": 9.0,  "India_Super_ECBC": 6.0,
                   "Indonesia": 7.53, "Vietnam": 13, "Thailand": 10,
                   "Cambodia": 7.53, "leed": 7.5},
    # India publishes no residential LPD; the workbook leaves it blank.
    "Residential": {"India": None, "India_ECBC+": None, "India_Super_ECBC": None,
                    "Indonesia": 7.53, "Vietnam": 8, "Thailand": 12,
                    "Cambodia": 7.53, "leed": 7.0},
}


# --------------------------------------------------------------------------
# conversion
# --------------------------------------------------------------------------

def cop_to_kw_per_rt(cop) -> Optional[Decimal]:
    """Dimensionless coefficient of performance -> kW of input per ton of cooling.

    The workbook states every cooling benchmark in kW/RT. BEAT stores what the
    user read off the label, which for an air conditioner is COP, EER, ISEER,
    CSPF or SEER, and for a chiller is already kW/RT. Without this bridge the
    two cannot be compared at all.

        kW/RT = kW(cooling) per ton / COP = 3.516 / COP

    A COP of 4.14 is 0.85 kW/RT, which is India's split-unit baseline.
    """
    try:
        cop = Decimal(str(cop))
    except (TypeError, ValueError, ArithmeticError):
        return None
    if cop <= 0:
        return None
    return KW_PER_REFRIGERATION_TON / cop


def kw_per_rt_to_cop(kw_per_rt) -> Optional[Decimal]:
    """The inverse, for showing a benchmark in the unit the user entered."""
    try:
        v = Decimal(str(kw_per_rt))
    except (TypeError, ValueError, ArithmeticError):
        return None
    if v <= 0:
        return None
    return KW_PER_REFRIGERATION_TON / v


# --------------------------------------------------------------------------
# resolution
# --------------------------------------------------------------------------

def _best_practice_is_credible(national, best, direction) -> bool:
    """Reject a best-practice value that is not better than the national baseline.

    This is a data guard, not a correction. ``1_System_Efficiency`` gives the
    split unit a LEED value of 1.36 kW/RT against national baselines of 0.80 to
    0.85 - LEED "best practice" 60% worse than the average building it is
    supposed to improve on. Used unchecked it produces a negative saving, which
    the UI would render as a building that gets worse by modernising.

    Refusing the row shows "no benchmark published" instead, which is both
    honest and the workbook's own convention for a value it cannot supply.
    """
    if national is None or best is None:
        return False
    if direction == LOWER_IS_BETTER:
        return best < national
    return best > national


def resolve_system_benchmark(system_key, country, standard=None):
    """Return the benchmark row for a system in a country, and the target to
    compare a building's own equipment against.

    ``standard`` pins LEED or EDGE; left alone, the better credible one wins.

    **The target falls back to the national baseline.** Taking best practice or
    nothing would have made Layer 2 silent for 287 of the 351 air conditioners
    in the database. The split-unit row is the reason: LEED is refused for
    being worse than every national baseline, and EDGE (0.86) is not better
    than India 0.85, Indonesia 0.84, Thailand 0.80 or Cambodia 0.84 either, so
    only Vietnam qualifies - and Vietnam has no split records.

    The national baseline is a published, sourced figure in its own right, so
    "your split runs at COP 2.8 against a national baseline of COP 4.14" is a
    real comparison, not an invented one. ``target_basis`` says which was used
    so the UI never calls a national average "best practice".
    """
    spec = SYSTEM_EFFICIENCY.get(system_key)
    if not spec:
        return None
    national = spec["national"].get(country)
    if national is None:
        return None
    direction = spec["direction"]

    candidates = [standard] if standard else ["leed", "edge"]
    best, best_name = None, None
    for name in candidates:
        value = spec.get(name)
        if not _best_practice_is_credible(national, value, direction):
            continue
        if best is None or _is_better(value, best, direction):
            best, best_name = value, name

    if best is not None:
        target, basis = best, best_name.upper()
    else:
        target, basis = national, "national baseline"

    return {
        "system": system_key,
        "label": spec["label"],
        "unit": spec["unit"],
        "direction": direction,
        "national": national,
        "best_practice": best,
        "standard": best_name.upper() if best_name else None,
        "target": target,
        "target_basis": basis,
        "credible": best is not None,
    }


def _is_better(a, b, direction):
    return a < b if direction == LOWER_IS_BETTER else a > b


def efficiency_saving_fraction(current, target, direction) -> float:
    """Fraction of this system's energy saved by moving to ``target``.

    Energy is proportional to a lower-is-better figure (kW of input per ton of
    cooling, watts per m3/h of air) and inversely proportional to a
    higher-is-better one (COP, boiler efficiency). So:

        lower-is-better   saving = 1 - target/current
        higher-is-better  saving = 1 - current/target

    Equipment already at or beyond the target saves nothing - it returns 0.0
    rather than a negative number, because "your chiller is better than best
    practice" is not a saving the building can bank twice.
    """
    try:
        current = Decimal(str(current))
        target = Decimal(str(target))
    except (TypeError, ValueError, ArithmeticError):
        return 0.0
    if current <= 0 or target <= 0:
        return 0.0
    if direction == LOWER_IS_BETTER:
        if target >= current:
            return 0.0
        return float(1 - (target / current))
    if target <= current:
        return 0.0
    return float(1 - (current / target))
