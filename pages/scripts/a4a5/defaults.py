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
  A4  = (mass_kg/1000) x SUM(leg_km x leg_ef)          [tonne-km; EF embeds load + empty running]
  A5w = waste_frac x (A1A3 + A4)  +  wasted_mass x disposal_EF

Why A4 is modelled as legs
--------------------------
A journey is not one vehicle. "Imported" is a ship followed by a truck, and a
national haul in India is largely rail followed by a truck. Each mode has its
own emission factor, so the only honest model is a list of legs summed
together.

An earlier version collapsed every scenario into one distance and one
"blended" factor. That produced the reading that **the emission factor falls as
distance rises** — India showed 0.070 for a 50 km local haul and 0.01286 for a
3,150 km import. Nothing was wrong with the arithmetic (sea freight really is
about seven times cleaner per tonne-km than road, so an average dominated by a
3,000 km sea leg sits near the sea figure), but the number on screen was a
weighted average of two different vehicles and was not a property of anything
real. Legs are reported separately now, and no blended figure is shown.
"""

# --- Freight emission factors, kg CO2e per tonne-km --------------------------
#
# INDIA is sourced. The other four are GLEC regional defaults standing in for
# national figures that do not exist yet, and the panel labels them as proxies
# rather than presenting them as equals.
#
# India — Smart Freight Centre / TCI-IIMB
# ---------------------------------------
# "India Default GHG Emission Values", Version 1, Smart Freight Centre with the
# TCI-IIMB Supply Chain Sustainability Lab at IIM Bangalore. Aligned to
# ISO 14083 and the GLEC Framework.
#
# These are published **directly as kg CO2e per tonne-km, well-to-wheel**, so
# nothing has to be derived. Everything an estimate would otherwise have to
# assume is measured in the study:
#
#   * CO2e on IPCC AR6 GWP100, including CH4 and N2O
#   * WTT (fuel supply) and TTW (combustion) given separately; WTW is their sum
#   * empty running measured per class (10.8%-14.4%)
#   * vehicle utilisation measured per class (67%-83%)
#   * a 5% DAF uplift for out-of-route deviation
#
# Road, WTW kg CO2e/tonne-km, diesel (study's table, page 6):
#
#   Small commercial       GVW <3.5 t    payload 0.5-2 t     0.3795
#   Medium commercial 1    GVW 3-5 t     payload 2-3.5 t     0.2222
#   Medium commercial 2    GVW 5-12 t    payload 3.5-8 t     0.1400
#   Heavy commercial 1     GVW 12-20 t   payload 8-12 t      0.0902   <- local
#   Heavy commercial 2     GVW 20-30 t   payload 12-20 t     0.0823   <- line haul
#   Heavy commercial 3     GVW 30-50 t   payload 20-40 t     0.0663
#   Tractor trailer        GVW 30-60 t   payload 20-50 t     0.0551
#
# The class is matched to the journey rather than flattened to one number: a
# 50 km delivery runs on a smaller, less efficient truck than a 300 km line
# haul, and the study's own class split is what lets us say so.
#
# Rail: WTT 0.0064 + TTW 0.0041 = 0.0106, averaged over 2015-16 to 2019-20 from
# Ministry of Railways annual reports.
#
# The study notes its road values "seem to be on the lower side" and rest on
# sample primary research that will be updated over time.
#
# Cross-check, for the record: deriving a factor independently from WRI's
# "India Specific Road Transport Emission Factors" v1.0 (2015) — a consultation
# draft giving kg CO2 per vehicle-km — gave 0.0807 for a 16 t payload HDV after
# adding CO2e, well-to-wheel and empty-running uplifts by hand. That is within
# 2% of SFC's measured 0.0823. SFC is used because it needs none of those
# assumptions.
SFC_INDIA_ROAD = {
    "scv": 0.3795, "mcv1": 0.2222, "mcv2": 0.1400,
    "hcv1": 0.0902, "hcv2": 0.0823, "hcv3": 0.0663, "trailer": 0.0551,
}
SFC_INDIA_RAIL = 0.0106

# Which road class carries which leg. Keyed by scenario; "default" covers the
# rest. Only India has the class data to make this distinction.
INDIA_ROAD_CLASS_BY_SCENARIO = {
    "local": "hcv1",        # short delivery, 12-20 t GVW
    "default": "hcv2",      # line haul and the inland leg off a port, 20-30 t
}
VEHICLE_CLASS_LABEL = {
    "scv": "small commercial, GVW <3.5 t",
    "mcv1": "medium commercial, GVW 3-5 t",
    "mcv2": "medium commercial, GVW 5-12 t",
    "hcv1": "heavy commercial, GVW 12-20 t",
    "hcv2": "heavy commercial, GVW 20-30 t",
    "hcv3": "heavy commercial, GVW 30-50 t",
    "trailer": "tractor trailer, GVW 30-60 t",
}

_GLEC = "GLEC v3 regional default — proxy, no national study found"
_SFC = ("Smart Freight Centre / TCI-IIMB, India Default GHG Emission Values v1 "
        "(ISO 14083, well-to-wheel, measured empty running and load factor)")

# road / rail / sea. Keyed by Country.name.
COUNTRY_TRANSPORT_EF = {
    "India":     {"road": SFC_INDIA_ROAD["hcv2"], "rail": SFC_INDIA_RAIL, "sea": 0.010,
                  "source": _SFC, "road_sourced": True},
    "Thailand":  {"road": 0.090, "rail": 0.020, "sea": 0.010,
                  "source": _GLEC, "road_sourced": False},
    "Cambodia":  {"road": 0.100, "rail": 0.025, "sea": 0.010,
                  "source": _GLEC, "road_sourced": False},
    "Vietnam":   {"road": 0.100, "rail": 0.025, "sea": 0.010,
                  "source": _GLEC, "road_sourced": False},
    "Indonesia": {"road": 0.100, "rail": 0.025, "sea": 0.010,
                  "source": _GLEC, "road_sourced": False},
}
DEFAULT_TRANSPORT_EF = {"road": 0.100, "rail": 0.025, "sea": 0.010,
                        "source": _GLEC, "road_sourced": False}


def road_ef(country_name: str, scenario: str):
    """(factor, vehicle-class label or None) for a road leg on this journey.

    Only India carries per-class data. Everywhere else returns the single
    regional road factor, with no class claimed.
    """
    ef = transport_ef(country_name)
    if country_name == "India":
        key = INDIA_ROAD_CLASS_BY_SCENARIO.get(
            scenario, INDIA_ROAD_CLASS_BY_SCENARIO["default"])
        return SFC_INDIA_ROAD[key], VEHICLE_CLASS_LABEL[key]
    return ef["road"], None


# --- Share of a NATIONAL land haul carried by rail ----------------------------
# ⚠️ ASSUMPTION, not sourced. These shares are judgement about how much of a
# ~300 km domestic freight movement realistically goes by rail rather than road,
# and they are the least defensible numbers in this file. They matter: India's
# rail factor (0.008) is roughly a ninth of its road factor (0.070), so the
# share moves A4 for every nationally-sourced material.
#
# Rationale for the current values, to be replaced with real modal-split data:
#   India      0.60  dedicated freight corridors; cement and steel move by rail
#   Thailand   0.30  rail freight exists but road dominates
#   Vietnam    0.20  north-south line used for bulk, limited capacity
#   Indonesia  0.10  archipelago; rail freight is Java-only and marginal
#   Cambodia   0.00  negligible rail freight — treat as all road
#
# Local and imported hauls use no rail: a 50 km local delivery and the inland
# leg off a port are both road in practice.
NATIONAL_RAIL_SHARE = {
    "India": 0.60,
    "Thailand": 0.30,
    "Vietnam": 0.20,
    "Indonesia": 0.10,
    "Cambodia": 0.00,
}
DEFAULT_NATIONAL_RAIL_SHARE = 0.0

# --- Sourcing scenarios (RICS Table 17 style) ---------------------------------
# land_km  : distance over land, split road/rail by NATIONAL_RAIL_SHARE when
#            rail_eligible, otherwise all road.
# sea_km   : sea leg, 0 for domestic scenarios.
SCENARIOS = {
    "local":    {"land_km": 50,  "sea_km": 0,    "rail_eligible": False,
                 "label": "Local (~50 km road)"},
    "national": {"land_km": 300, "sea_km": 0,    "rail_eligible": True,
                 "label": "National (~300 km rail + road)"},
    "imported": {"land_km": 150, "sea_km": 3000, "rail_eligible": False,
                 "label": "Imported (~3,000 km sea + 150 km road)"},
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


def national_rail_share(country_name: str) -> float:
    return NATIONAL_RAIL_SHARE.get(country_name, DEFAULT_NATIONAL_RAIL_SHARE)


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


def scenario_legs(scenario: str, country_name: str) -> list[dict]:
    """The journey for a sourcing scenario, one entry per transport mode.

    Returns a list of {"mode", "km", "ef"} in the order travelled. A4 is the sum
    of km x ef across them, so each leg can be shown and reasoned about on its
    own terms. Legs of zero length are left out.
    """
    ef = transport_ef(country_name)
    key = scenario if scenario in SCENARIOS else "national"
    scen = SCENARIOS[key]
    legs = []

    sea_km = float(scen["sea_km"])
    if sea_km > 0:
        legs.append({"mode": "sea", "km": round(sea_km, 1), "ef": round(ef["sea"], 5)})

    land_km = float(scen["land_km"])
    rail_share = national_rail_share(country_name) if scen["rail_eligible"] else 0.0
    rail_km = land_km * rail_share
    road_km = land_km - rail_km
    if rail_km > 0:
        legs.append({"mode": "rail", "km": round(rail_km, 1), "ef": round(ef["rail"], 5)})
    if road_km > 0:
        # the road class depends on the journey: a short delivery runs on a
        # smaller, less efficient truck than a line haul
        rf, _cls = road_ef(country_name, key)
        legs.append({"mode": "road", "km": round(road_km, 1), "ef": round(rf, 5)})

    return legs


def road_class_for(scenario: str, country_name: str):
    # The vehicle class behind a journey road leg, or None where unknown.
    key = scenario if scenario in SCENARIOS else "national"
    return road_ef(country_name, key)[1]


def legs_tonne_km_co2(legs) -> float:
    """kg CO2e per tonne carried, summed over the legs."""
    return sum(float(l["km"]) * float(l["ef"]) for l in legs)


def effective_ef(legs) -> float:
    """Distance-weighted mean factor across the legs.

    Reporting this as "the emission factor" is what made the old output look
    wrong, so it is NOT shown anywhere. It exists for one purpose: filling in
    the missing half of a half-specified per-material override (a user who sets
    a distance but no factor, or the reverse).
    """
    total_km = sum(float(l["km"]) for l in legs)
    if not total_km:
        return 0.0
    return legs_tonne_km_co2(legs) / total_km


def scenario_total_km(legs) -> float:
    return round(sum(float(l["km"]) for l in legs), 1)


def describe_legs(legs) -> str:
    """One-line human reading of a journey, e.g. 'sea 3000 km @ 0.01 + road 150 km @ 0.07'."""
    return " + ".join("%s %g km @ %g" % (l["mode"], l["km"], l["ef"]) for l in legs) or "—"
