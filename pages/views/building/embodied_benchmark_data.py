"""
Embodied carbon benchmark dataset and calculation helpers.

Source: docs/Embodied Benchmark.xlsx (Ranking + Savings sheets)
Logic:  docs/Embodiedcarbon_Benchmark_Logic.docx
"""

# ---------------------------------------------------------------------------
# Ranking dataset — Country / State / Building Type combinations
# Countries with no data: Indonesia, Thailand, Vietnam
# ---------------------------------------------------------------------------

RANKING_DATA = [
    # India — Uttar Pradesh
    {
        "country": "India", "state": "Uttar Pradesh",
        "climate_zone": "Composite", "seismic_zone": "Zone III",
        "building_type": "Commercial Building",
        "best_practice": 214.9, "national_average": 335.4,
        "num_buildings": 35, "year_range": "2024–2025",
    },
    {
        "country": "India", "state": "Uttar Pradesh",
        "climate_zone": "Composite", "seismic_zone": "Zone III",
        "building_type": "Residential Building",
        "best_practice": 201.9, "national_average": 565.1,
        "num_buildings": 28, "year_range": "2024–2025",
    },
    {
        "country": "India", "state": "Uttar Pradesh",
        "climate_zone": "Composite", "seismic_zone": "Zone III",
        "building_type": "Institutional/Public Building",
        "best_practice": 242.2, "national_average": 334.0,
        "num_buildings": 30, "year_range": "2024–2025",
    },
    # India — Haryana
    {
        "country": "India", "state": "Haryana",
        "climate_zone": "Composite", "seismic_zone": "Zone IV",
        "building_type": "Commercial Building",
        "best_practice": 228.1, "national_average": 412.3,
        "num_buildings": 42, "year_range": "2024–2025",
    },
    {
        "country": "India", "state": "Haryana",
        "climate_zone": "Composite", "seismic_zone": "Zone IV",
        "building_type": "Residential Building",
        "best_practice": 210.5, "national_average": 498.7,
        "num_buildings": 37, "year_range": "2024–2025",
    },
    {
        "country": "India", "state": "Haryana",
        "climate_zone": "Composite", "seismic_zone": "Zone IV",
        "building_type": "Institutional/Public Building",
        "best_practice": 251.3, "national_average": 389.6,
        "num_buildings": 25, "year_range": "2024–2025",
    },
    # India — Maharashtra
    {
        "country": "India", "state": "Maharashtra",
        "climate_zone": "Hot-dry", "seismic_zone": "Zone III",
        "building_type": "Commercial Building",
        "best_practice": 258.4, "national_average": 4383.7,
        "num_buildings": 53, "year_range": "2024–2025",
    },
    {
        "country": "India", "state": "Maharashtra",
        "climate_zone": "Hot-dry", "seismic_zone": "Zone III",
        "building_type": "Residential Building",
        "best_practice": 232.6, "national_average": 521.4,
        "num_buildings": 45, "year_range": "2024–2025",
    },
    {
        "country": "India", "state": "Maharashtra",
        "climate_zone": "Hot-dry", "seismic_zone": "Zone III",
        "building_type": "Institutional/Public Building",
        "best_practice": 267.9, "national_average": 418.2,
        "num_buildings": 31, "year_range": "2024–2025",
    },
    # India — Kerala
    {
        "country": "India", "state": "Kerala",
        "climate_zone": "Composite", "seismic_zone": "Zone III",
        "building_type": "Commercial Building",
        "best_practice": 241.7, "national_average": 398.5,
        "num_buildings": 38, "year_range": "2024–2025",
    },
    {
        "country": "India", "state": "Kerala",
        "climate_zone": "Composite", "seismic_zone": "Zone III",
        "building_type": "Residential Building",
        "best_practice": 219.1, "national_average": 703.3,
        "num_buildings": 29, "year_range": "2024–2025",
    },
    {
        "country": "India", "state": "Kerala",
        "climate_zone": "Composite", "seismic_zone": "Zone III",
        "building_type": "Institutional/Public Building",
        "best_practice": 219.1, "national_average": 703.3,
        "num_buildings": 29, "year_range": "2024–2025",
    },
    # Cambodia — Phnom Penh
    {
        "country": "Cambodia", "state": "Phnom Penh",
        "climate_zone": "Warm-humid", "seismic_zone": None,
        "building_type": "Commercial Building",
        "best_practice": 321.3, "national_average": 562.1,
        "num_buildings": 152, "year_range": "2024–2025",
    },
    {
        "country": "Cambodia", "state": "Phnom Penh",
        "climate_zone": "Warm-humid", "seismic_zone": None,
        "building_type": "Residential Building",
        "best_practice": 298.8, "national_average": 510.3,
        "num_buildings": 22, "year_range": "2024–2025",
    },
    {
        "country": "Cambodia", "state": "Phnom Penh",
        "climate_zone": "Warm-humid", "seismic_zone": None,
        "building_type": "Institutional/Public Building",
        "best_practice": 364.1, "national_average": 564.6,
        "num_buildings": 41, "year_range": "2024–2025",
    },
]

# Countries explicitly excluded from benchmark (no data in dataset)
NO_DATA_COUNTRIES = {"indonesia", "thailand", "vietnam"}

# ---------------------------------------------------------------------------
# Savings reduction table — from Savings sheet
# Keys must exactly match output buckets of _MATERIAL_CATEGORY_MAPPING
# ---------------------------------------------------------------------------

SAVINGS_DATA = {
    "Readymixconcrete & cement": {"method": "with GGBS/Fly Ash", "reduction_pct": 0.25},
    "Steel":                     {"method": "recycled content",   "reduction_pct": 0.20},
    "Rebar":                     {"method": "high recycled content", "reduction_pct": 0.30},
    "Pre-cast concrete":         {"method": "low-clinker/SCM Mix",   "reduction_pct": 0.22},
    "Wood/Timber":               {"method": "FSC/Engineered timber",  "reduction_pct": 0.40},
    "Masonry":                   {"method": "AAC Blocks",             "reduction_pct": 0.18},
    "Insulation materials":      {"method": "low carbon options (mineral wool/wood fibre/cellulose)", "reduction_pct": 0.15},
    "Finishing materials":       {"method": "low-EC finishes package (paints, flooring, internal linings)", "reduction_pct": 0.20},
    "Aluminium & other metals":  {"method": "high recycled / low carbon smelting", "reduction_pct": 0.40},
    "Others":                    {"method": None, "reduction_pct": 0.0},
}

# ---------------------------------------------------------------------------
# Benchmark lookup
# ---------------------------------------------------------------------------

def get_benchmark_for_building(building):
    """
    Return the matching RANKING_DATA entry for the building, or None if
    no match exists (including countries with no dataset coverage).

    Matching logic:
      1. country name (case-insensitive)
      2. state/region name (case-insensitive, partial match allowed)
      3. building type (case-insensitive substring match)
    """
    try:
        country_name = (building.country.name or "").lower().strip() if building.country else ""
    except AttributeError:
        country_name = ""

    if not country_name:
        return None

    if country_name in NO_DATA_COUNTRIES:
        return None

    try:
        state_name = (building.region.name or "").lower().strip() if building.region else ""
    except AttributeError:
        state_name = ""

    try:
        btype = (building.category.category.name or "").lower().strip() if building.category and building.category.category else ""
    except AttributeError:
        btype = ""

    for entry in RANKING_DATA:
        if entry["country"].lower() != country_name:
            continue

        entry_state = entry["state"].lower()
        if state_name and entry_state and entry_state not in state_name and state_name not in entry_state:
            continue

        entry_btype = entry["building_type"].lower()
        if btype and not (btype in entry_btype or entry_btype in btype):
            continue

        return entry

    # If no state/type match, fall back to country-level first entry
    for entry in RANKING_DATA:
        if entry["country"].lower() == country_name:
            return entry

    return None


# ---------------------------------------------------------------------------
# Benchmark position calculation
# ---------------------------------------------------------------------------

def calculate_benchmark_position(embodied_carbon, benchmark_entry):
    """
    Calculate where the building sits on the benchmark scale.

    Args:
        embodied_carbon: float or Decimal — building's total embodied carbon (kgCO2eq/m²)
        benchmark_entry: dict from RANKING_DATA

    Returns:
        dict with position info, or None if calculation not possible.
    """
    if not benchmark_entry:
        return None

    ec = float(embodied_carbon)
    best = benchmark_entry["best_practice"]
    avg = benchmark_entry["national_average"]
    scale = avg - best

    if scale <= 0:
        return None

    raw_position = (ec - best) / scale * 100
    position_pct = max(0.0, min(100.0, raw_position))
    better_than_pct = round((1 - position_pct / 100) * 100)

    # Tier badge thresholds (docx §Step 5)
    if ec <= best:
        tier = "Exceeds Best Practice 🏆"
        tier_class = "exceeds"
    elif ec <= best + scale * 0.25:
        tier = "Top 25% tier"
        tier_class = "top25"
    elif ec <= best + scale * 0.50:
        tier = "Top 50% tier"
        tier_class = "top50"
    elif ec <= best + scale * 0.75:
        tier = "Above Average"
        tier_class = "above_avg"
    else:
        tier = "Below Average"
        tier_class = "below_avg"

    return {
        "position_pct": round(position_pct, 1),
        "better_than_pct": better_than_pct,
        "tier": tier,
        "tier_class": tier_class,
        "best_practice": best,
        "national_average": avg,
        "num_buildings": benchmark_entry["num_buildings"],
        "year_range": benchmark_entry["year_range"],
        "climate_zone": benchmark_entry.get("climate_zone"),
        "seismic_zone": benchmark_entry.get("seismic_zone"),
        "building_type": benchmark_entry["building_type"],
    }


# ---------------------------------------------------------------------------
# Savings / optimisation calculations (Figures 2 & 3)
# ---------------------------------------------------------------------------

def get_embodied_savings_data(embodied_by_material):
    """
    Calculate per-material optimisation savings from Figure 1 data.

    Args:
        embodied_by_material: dict returned by get_embodied_carbon_by_material()
            keys: 'labels', 'data' (% share), 'absolute' (kgCO2eq/m²), 'total'

    Returns:
        dict with 'materials' list and aggregated totals, safe for JSON serialisation.
    """
    labels = embodied_by_material.get("labels", [])
    data = embodied_by_material.get("data", [])      # % shares
    absolute = embodied_by_material.get("absolute", [])
    total_baseline = embodied_by_material.get("total", 0.0) or 0.0

    materials = []
    total_saving = 0.0

    for i, label in enumerate(labels):
        share_pct = float(data[i]) if i < len(data) else 0.0
        baseline_ec = float(absolute[i]) if i < len(absolute) else 0.0

        savings_entry = SAVINGS_DATA.get(label, {"method": None, "reduction_pct": 0.0})
        reduction_pct = savings_entry["reduction_pct"]
        method = savings_entry["method"]

        potential_saving = round(baseline_ec * reduction_pct, 2)
        optimised_ec = round(baseline_ec - potential_saving, 2)

        # Bar widths as % of total_baseline for proportional display
        baseline_bar_pct = round((baseline_ec / total_baseline * 100), 1) if total_baseline > 0 else 0.0
        saving_bar_pct = round((potential_saving / total_baseline * 100), 1) if total_baseline > 0 else 0.0

        materials.append({
            "label": label,
            "share_pct": round(share_pct, 1),
            "baseline_ec": round(baseline_ec, 1),
            "reduction_pct": reduction_pct,
            "reduction_pct_display": int(reduction_pct * 100),
            "method": method,
            "potential_saving": round(potential_saving, 1),
            "optimised_ec": round(optimised_ec, 1),
            "baseline_bar_pct": baseline_bar_pct,
            "saving_bar_pct": saving_bar_pct,
            "has_reduction": reduction_pct > 0 and method is not None,
        })

        total_saving += potential_saving

    total_saving = round(total_saving, 1)
    total_optimised = round(total_baseline - total_saving, 1)
    reduction_overall = round((total_saving / total_baseline * 100), 1) if total_baseline > 0 else 0.0

    return {
        "materials": materials,
        "total_baseline_ec": round(total_baseline, 1),
        "total_saving": total_saving,
        "total_optimised_ec": total_optimised,
        "reduction_pct": reduction_overall,
    }
