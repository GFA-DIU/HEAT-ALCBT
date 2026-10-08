"""Compute A4 (transport) and A5w (construction waste) for one material.

Per m² of floor area, consistent with BEAT's A1–A3 aggregation. A4/A5 are always
estimated from project (country + scenario) assumptions — EPD-declared A4/A5 is not
used (A4/A5 are site-specific, not product-specific). A1–A3 still comes from the EPD.

    A4  = (mass_kg / 1000) x distance_km x ef        (tonne-km; ef embeds load + empty running)
    A5w = waste_frac x (A1A3 + A4)  +  (wasted_mass x disposal_ef)

Overrides (per material, else country/category default):
    scenario     : local | national | imported   -> sets distance + ef
    distance_km  : explicit A4 distance
    ef           : explicit A4 emission factor (kg CO2e/tonne-km)
    waste_rate   : explicit A5 waste fraction
"""
from decimal import Decimal

from pages.scripts.a4a5 import defaults as D


def material_a4_a5(
    *,
    a1a3_per_m2: Decimal,
    mass_kg,
    floor_area,
    country_name: str,
    category_name: str | None,
    scenario: str | None = None,
    waste_rate: float | None = None,
    distance_km: float | None = None,
    ef: float | None = None,
):
    """Return (a4_per_m2, a5w_per_m2, assumptions_dict)."""
    fa = Decimal(str(floor_area or 0))
    scen_key = scenario or D.default_scenario(category_name)
    # scenario defaults for distance + ef, then apply explicit overrides
    d_def, e_def = D.scenario_distance_ef(scen_key, country_name)
    dist = float(distance_km) if distance_km is not None else d_def
    efv = float(ef) if ef is not None else e_def
    wr = float(waste_rate) if waste_rate is not None else D.default_waste_rate(category_name)

    if mass_kg is None or fa <= 0:
        return Decimal("0"), Decimal("0"), {
            "scenario": scen_key, "distance_km": dist, "ef": efv,
            "waste_rate": wr, "mass_kg": None,
            "note": "mass not derivable — A4/A5 skipped" if mass_kg is None else "no floor area",
        }

    mass = Decimal(str(mass_kg))
    tonnes = mass / Decimal("1000")

    a4_total = tonnes * Decimal(str(dist)) * Decimal(str(efv))
    a4_per_m2 = a4_total / fa

    disposal_total = mass * Decimal(str(wr)) * Decimal(str(D.DISPOSAL_EF_PER_KG))
    a5w_per_m2 = Decimal(str(wr)) * (Decimal(str(a1a3_per_m2)) + a4_per_m2) + disposal_total / fa

    return a4_per_m2, a5w_per_m2, {
        "scenario": scen_key,
        "distance_km": round(dist, 1),
        "ef": round(efv, 5),
        "waste_rate": round(wr, 4),
        "mass_kg": float(round(mass, 1)),
        "disposal_ef": D.DISPOSAL_EF_PER_KG,
        "ef_source": D.transport_ef(country_name)["source"],
    }
