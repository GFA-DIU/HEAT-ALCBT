"""Compute A4 (transport) and A5w (construction waste) for one material.

Per m² of floor area, consistent with BEAT's A1–A3 aggregation. A4/A5 are always
estimated from project (country + scenario) assumptions — EPD-declared A4/A5 is not
used (A4/A5 are site-specific, not product-specific). A1–A3 still comes from the EPD.

    A4  = (mass_kg / 1000) x SUM(leg_km x leg_ef)   (tonne-km; ef embeds load + empty running)
    A5w = waste_frac x (A1A3 + A4)  +  (wasted_mass x disposal_ef)

A journey is a list of legs, one per transport mode — a ship then a truck, or
rail then a truck — because each mode has its own emission factor. See
``defaults.scenario_legs``.

Overrides (per material, else country/category default):
    scenario     : local | national | imported   -> sets the legs
    distance_km  : explicit A4 distance          -> collapses to ONE custom leg
    ef           : explicit A4 emission factor   -> collapses to ONE custom leg
    waste_rate   : explicit A5 waste fraction

Setting a distance or a factor by hand replaces the whole journey with a single
leg, because a user who types "400 km" means one trip of 400 km, not a reshuffle
of the sea and road legs behind it. Supplying only one of the two fills the other
from the scenario it replaces.
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
    legs = D.scenario_legs(scen_key, country_name)

    # A hand-set distance or factor replaces the journey with one explicit leg.
    if distance_km is not None or ef is not None:
        legs = [{
            "mode": "custom",
            "km": round(float(distance_km) if distance_km is not None
                        else D.scenario_total_km(legs), 1),
            "ef": round(float(ef) if ef is not None else D.effective_ef(legs), 5),
        }]

    wr = float(waste_rate) if waste_rate is not None else D.default_waste_rate(category_name)
    per_tonne = D.legs_tonne_km_co2(legs)

    meta = {
        "scenario": scen_key,
        "legs": legs,
        "legs_text": D.describe_legs(legs),
        "distance_km": D.scenario_total_km(legs),
        "kgco2e_per_tonne": round(per_tonne, 4),
        "waste_rate": round(wr, 4),
        "disposal_ef": D.DISPOSAL_EF_PER_KG,
        "ef_source": D.transport_ef(country_name)["source"],
        "rail_share": (D.national_rail_share(country_name)
                       if D.SCENARIOS.get(scen_key, {}).get("rail_eligible") else 0.0),
    }

    if mass_kg is None or fa <= 0:
        meta["mass_kg"] = None
        meta["note"] = ("mass not derivable — A4/A5 skipped" if mass_kg is None
                        else "no floor area")
        return Decimal("0"), Decimal("0"), meta

    mass = Decimal(str(mass_kg))
    tonnes = mass / Decimal("1000")

    a4_total = tonnes * Decimal(str(per_tonne))
    a4_per_m2 = a4_total / fa

    disposal_total = mass * Decimal(str(wr)) * Decimal(str(D.DISPOSAL_EF_PER_KG))
    a5w_per_m2 = Decimal(str(wr)) * (Decimal(str(a1a3_per_m2)) + a4_per_m2) + disposal_total / fa

    meta["mass_kg"] = float(round(mass, 1))
    return a4_per_m2, a5w_per_m2, meta
