"""A4–A5 upfront-carbon default assumptions (RICS WLCA 2nd ed. structure).

Version-controlled, auditable config — NOT edited in-app per session. End users
adjust A4/A5 per material (sourcing scenario + waste %); these tables are the
country/methodology defaults behind that.

Values here are **representative v1 defaults** to make the feature runnable and
testable locally. Refine against source at build-out:
  - India road/rail: SFC/WRI "India Default GHG Emission Values" v1.0 (May 2025), GLEC/ISO 14083
  - Thailand: TGO national EF database
  - Cambodia/Vietnam/Indonesia: GLEC v3 regional default (no national study found)
  - Distances & waste rates: RICS WLCA 2nd ed. Table 17 (transport) & Table 18 (waste)

Method (see docs/a4_a5_upfront_carbon_scope.md):
  A4  = (mass_kg/1000) x distance_km x EF_mode         [tonne-km; EF already embeds load + empty running]
  A5w = waste_frac x (A1A3 + A4)  +  wasted_mass x disposal_EF
"""

# --- Freight emission factors, kg CO2e per tonne-km (well-to-wheel) -----------
# road / rail / sea. Keyed by Country.name.
COUNTRY_TRANSPORT_EF = {
    "India":     {"road": 0.070, "rail": 0.008, "sea": 0.010, "source": "SFC/WRI India Default GHG Values v1.0 (2025)"},
    "Thailand":  {"road": 0.090, "rail": 0.020, "sea": 0.010, "source": "TGO (placeholder — lock exact)"},
    "Cambodia":  {"road": 0.100, "rail": 0.025, "sea": 0.010, "source": "GLEC v3 regional default"},
    "Vietnam":   {"road": 0.100, "rail": 0.025, "sea": 0.010, "source": "GLEC v3 regional default"},
    "Indonesia": {"road": 0.100, "rail": 0.025, "sea": 0.010, "source": "GLEC v3 regional default"},
}
DEFAULT_TRANSPORT_EF = {"road": 0.100, "rail": 0.025, "sea": 0.010, "source": "GLEC v3 default"}

# --- Sourcing scenarios → distance (km) + mode (RICS Table 17 style) ----------
# 'imported' has a sea leg (origin→nearest port) + inland road leg.
SCENARIOS = {
    "local":    {"road_km": 50,   "sea_km": 0,    "label": "Local (~50 km road)"},
    "national": {"road_km": 300,  "sea_km": 0,    "label": "National (~300 km road)"},
    "imported": {"road_km": 150,  "sea_km": 3000, "label": "Imported (sea + ~150 km inland)"},
}
SCENARIO_CHOICES = [("local", "Local"), ("national", "National"), ("imported", "Imported")]

# --- Default scenario per material category (keyword match on category name) --
_SCENARIO_KEYWORDS = [
    ("imported", ("steel", "alumin", "glass", "copper", "zinc")),
    ("local",    ("concrete", "cement", "aggregate", "sand", "block", "brick",
                  "aac", "mortar", "plaster", "screed", "terrazzo", "lime", "stone",
                  "laterite", "rammed earth", "cseb")),
    # everything else defaults to 'national'
]

# --- Construction waste rates (fraction of installed qty; RICS Table 18) ------
_WASTE_KEYWORDS = [
    (("plasterboard", "gypsum"), 0.20),
    (("block", "brick", "aac", "aerated", "masonry"), 0.15),
    (("cement", "mortar", "render", "plaster", "screed"), 0.12),
    (("tile", "ceramic"), 0.10),
    (("wood", "timber", "plywood"), 0.10),
    (("insulation",), 0.10),
    (("glass", "alumin"), 0.05),
    (("concrete",), 0.05),
    (("steel", "rebar", "reinforc"), 0.05),
]
DEFAULT_WASTE_RATE = 0.08

# --- Site waste disposal EF (kg CO2e per kg wasted; RICS Table 19 landfill) ---
# C2 transport-to-disposal + C4 landfill, simplified default. Refine per material.
DISPOSAL_EF_PER_KG = 0.010


def transport_ef(country_name: str) -> dict:
    return COUNTRY_TRANSPORT_EF.get(country_name, DEFAULT_TRANSPORT_EF)


def default_scenario(category_name: str | None) -> str:
    name = (category_name or "").lower()
    for scenario, kws in _SCENARIO_KEYWORDS:
        if any(k in name for k in kws):
            return scenario
    return "national"


def default_waste_rate(category_name: str | None) -> float:
    name = (category_name or "").lower()
    for kws, rate in _WASTE_KEYWORDS:
        if any(k in name for k in kws):
            return rate
    return DEFAULT_WASTE_RATE


def scenario_distance_ef(scenario: str, country_name: str):
    """Return (distance_km, ef_kg_per_tonne_km) for a sourcing scenario + country.

    A4 is modelled as a single leg: A4 = tonnes x distance x ef. For 'imported'
    the sea + inland legs are collapsed into one effective distance and a blended
    ef, so both numbers stay directly editable in the UI.
    """
    ef = transport_ef(country_name)
    scen = SCENARIOS.get(scenario, SCENARIOS["national"])
    road_km = float(scen["road_km"]); sea_km = float(scen["sea_km"])
    if sea_km > 0:
        total = sea_km + road_km
        blended = (sea_km * ef["sea"] + road_km * ef["road"]) / total if total else ef["road"]
        return round(total, 1), round(blended, 5)
    return round(road_km, 1), round(ef["road"], 5)
