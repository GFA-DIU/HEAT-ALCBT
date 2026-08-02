"""Plausibility ("does this make sense?") checks for a building's embodied-carbon
inputs and results.

The carbon calc will happily produce a number from corrupted data (a 5-metre-thick
granite slab, 1,210 "pieces" of door frame, a 240 m² hospital). These checks are a
sanity layer on top: they flag results and inputs that are implausible so a human
can catch them, instead of a wrong number silently flowing through.

Design
------
`check_building(building)` returns a flat list of `Flag` dicts:

    {"level": "error"|"warning", "code": str, "scope": "building"|"assembly"|"product",
     "target": str, "message": str}

It reuses the real calc (`calculate_impacts`) so "per-material contribution" means
exactly what the building total means. Thresholds are module constants — tune here.

Four families (all opt-in via the caller; this returns them all):
  1. building_total   — whole-building kgCO2/m² outside a sane band
  2. row_outlier      — a single material dominates or has absurd intensity
  3. suspicious_input — floor area, layer thickness, piece count, mixed units
  4. completeness     — missing classification (No category), EPD, or floor area
"""

from collections import defaultdict
from decimal import Decimal

from pages.models.epd import Unit
from pages.views.building.impact_calculation import (
    calculate_impacts,
    ImpactCalculationError,
)

# ------------------------------------------------------------------ thresholds
TOTAL_MIN = Decimal("50")       # kgCO2e/m² — below this a whole building is suspect
TOTAL_MAX = Decimal("2000")     # kgCO2e/m² — above this a whole building is suspect
ROW_DOMINANCE = Decimal("0.5")  # one material > 50% of the building total
ROW_INTENSITY_MAX = Decimal("5000")   # one material alone > this kgCO2e/m²
FLOOR_AREA_MIN = Decimal("30")  # m² — smaller than this is almost certainly wrong
THICKNESS_MAX_CM = Decimal("100")     # layer thickness > 1 m
PCS_MAX = Decimal("500")        # piece count this large is usually a mislabelled mass


def _flag(level, code, scope, target, message):
    return {"level": level, "code": code, "scope": scope,
            "target": target, "message": message}


def assembly_flags(assembly, products, assembly_gwp_per_m2):
    """Short 'doesn't make sense' labels for ONE assembly row, for the UI badge.

    Reuses the module thresholds. Excludes 'No category' (already shown as its own
    chip in the editor). `assembly_gwp_per_m2` is the row's total already normalised
    per floor area (as the editor computes it).
    """
    labels = []
    for sp in products:
        q = None
        try:
            q = Decimal(str(sp.quantity)) if sp.quantity is not None else None
        except Exception:
            q = None
        if q is not None and sp.input_unit == Unit.CM and q > THICKNESS_MAX_CM:
            labels.append("Layer thickness > 1 m — likely a corrupted quantity")
        if q is not None and sp.input_unit == Unit.PCS and q > PCS_MAX:
            labels.append("Piece count implausibly high — often a mislabelled mass")
    try:
        if Decimal(str(assembly_gwp_per_m2)) > ROW_INTENSITY_MAX:
            labels.append("Implausibly high carbon for one row — check quantities")
    except Exception:
        pass
    # stable, de-duplicated
    return sorted(set(labels))


def check_building(building):
    """Return a list of plausibility flags for one building. Never raises."""
    flags = []

    # -- floor area (needed for everything; flag if missing/tiny) --------------
    fa = getattr(building, "total_floor_area", None)
    try:
        fa_dec = Decimal(str(fa)) if fa is not None else None
    except Exception:
        fa_dec = None
    if fa_dec is None or fa_dec <= 0:
        flags.append(_flag("error", "floor_area_missing", "building",
                            building.name or str(building.pk),
                            "Total floor area is missing or zero — every kgCO2/m² value is unreliable."))
    elif fa_dec < FLOOR_AREA_MIN:
        flags.append(_flag("warning", "floor_area_small", "building",
                            building.name or str(building.pk),
                            f"Floor area is only {fa_dec} m² — implausibly small; inflates every per-m² value."))

    building_assemblies = list(building.buildingassembly_set.all())

    # -- walk products: totals, per-row contribution, input & completeness -----
    total = Decimal("0")
    contributions = []          # (label, assembly_name, contribution)
    epd_dimensions = defaultdict(set)   # epd_id -> {dimensions} for mixed-unit check

    for ba in building_assemblies:
        assembly = ba.assembly
        for sp in assembly.structuralproduct_set.all():
            epd = sp.epd
            label = (epd.name.strip() if epd else "Unknown EPD")

            # completeness
            if epd is None:
                flags.append(_flag("error", "missing_epd", "product",
                                    f"{assembly.name} — (no EPD)",
                                    "Product has no EPD assigned."))
                continue
            if sp.classification_id is None:
                flags.append(_flag("warning", "no_classification", "product",
                                    f"{assembly.name} — {label}",
                                    "No category: product has no classification assigned."))
            epd_dimensions[epd.pk].add(assembly.dimension)

            # suspicious inputs
            if sp.input_unit == Unit.CM and sp.quantity is not None \
                    and Decimal(str(sp.quantity)) > THICKNESS_MAX_CM:
                flags.append(_flag("warning", "thickness_implausible", "product",
                                   f"{assembly.name} — {label}",
                                   f"Layer thickness {sp.quantity} cm (> 1 m) — likely a corrupted quantity."))
            if sp.input_unit == Unit.PCS and sp.quantity is not None \
                    and Decimal(str(sp.quantity)) > PCS_MAX:
                flags.append(_flag("warning", "pcs_implausible", "product",
                                   f"{assembly.name} — {label}",
                                   f"Piece count {sp.quantity} — implausibly high; often a mislabelled mass."))

            # contribution to the total (reuse the real calc)
            try:
                impacts = calculate_impacts(
                    dimension=assembly.dimension,
                    assembly_quantity=ba.quantity,
                    total_floor_area=float(fa_dec) if fa_dec else 1.0,
                    p=sp,
                )
                c = Decimal("0")
                for imp in impacts:
                    it = imp["impact_type"]
                    if it.impact_category == "gwp" and it.life_cycle_stage == "a1a3":
                        v = Decimal(str(imp["impact_value"]))
                        if v > 0:
                            c += v
                total += c
                contributions.append((label, assembly.name, c))
            except (ImpactCalculationError, ValueError, AttributeError, ZeroDivisionError):
                # calc errors are surfaced elsewhere (the "cannot convert" list);
                # not a plausibility concern here.
                pass

    # -- mixed-unit: same EPD used across >1 assembly dimension ----------------
    for epd_id, dims in epd_dimensions.items():
        if len(dims) > 1:
            flags.append(_flag("warning", "mixed_units", "building",
                               building.name or str(building.pk),
                               f"An EPD is used across {len(dims)} different unit types "
                               f"({', '.join(sorted(str(d) for d in dims))}) — inconsistent data entry."))

    # -- per-row outliers ------------------------------------------------------
    for label, asm_name, c in contributions:
        if c > ROW_INTENSITY_MAX:
            flags.append(_flag("error", "row_intensity", "product",
                               f"{asm_name} — {label}",
                               f"Single material contributes {c:,.0f} kgCO2/m² — implausibly high."))
        elif total > 0 and c / total > ROW_DOMINANCE:
            flags.append(_flag("warning", "row_dominance", "product",
                               f"{asm_name} — {label}",
                               f"Single material is {c / total:.0%} of the building total — check its quantity."))

    # -- building total band ---------------------------------------------------
    if total > 0:
        if total > TOTAL_MAX:
            flags.append(_flag("error", "total_high", "building",
                               building.name or str(building.pk),
                               f"Building total {total:,.0f} kgCO2/m² is above the plausible range (> {TOTAL_MAX})."))
        elif total < TOTAL_MIN:
            flags.append(_flag("warning", "total_low", "building",
                               building.name or str(building.pk),
                               f"Building total {total:.0f} kgCO2/m² is below the plausible range (< {TOTAL_MIN})."))

    return flags
