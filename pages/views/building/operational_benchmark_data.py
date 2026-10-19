"""
Operational carbon benchmark dataset and calculation helpers (Layer 1).

Whole-building EPI (Energy Performance Index / EUI) benchmark: places a building's
actual annual energy use per m² against the national average and a country-specific
best-practice line, then converts both to carbon via the grid emission factor.

Source of truth:
    docs/BEAT_Operational_Savings_EUI_and_GridEF_CONSOLIDATED.xlsx —
      - National_Avg_EUI      -> NATIONAL_AVG_EUI  (all 5 countries)
      - BestPractice_India    -> BEST_PRACTICE_INDIA (national EPI x (1 - Super-ECBC%))
      - BestPractice_NonIndia -> LEED_BEST_PRACTICE
      - Grid_EF               -> GRID_EF_FALLBACK  (used only when no electricity EPD)
Logic:
    docs/Operational_Carbon_Savings_Methodology_and_Logic_v1.1.docx (§4, §5, §10)

Units: EUI in kWh/m²/yr; carbon in kgCO2eq/m²/yr; grid EF in kgCO2/kWh.
A missing (country, type, sub-type, climate) combination has no benchmark, so
Layer 1 is hidden for that building (the "blank cell -> hide" guard).
"""

# ---------------------------------------------------------------------------
# Climate mapping — ClimateType.name slug -> EPI/ECBC climate label
# (companion Climate_Mapping). "cold" has no EPI row and falls back to Composite
# with an approximation flag surfaced in the UI source line.
# ---------------------------------------------------------------------------

CLIMATE_TO_EPI_LABEL = {
    "hot-dry": ("Hot & Dry", False),
    "warm-humid": ("Warm & Humid", False),
    "composite": ("Composite", False),
    "temperate": ("Temperate", False),
    "tropical-wet": ("Tropical Wet", False),
    "cold": ("Composite", True),  # no Cold EPI row -> Composite fallback (approx.)
}

# ---------------------------------------------------------------------------
# Taxonomy mapping — (is_india, BuildingCategory.name, BuildingSubcategory.name)
#   -> (EPI building_type, EPI sub_type or None, is_approximation)
# Derived from the spec §4 table + load_india_building_categories.INDIA_CATEGORIES
# and migration 0002's global taxonomy. sub_type "by_ac" means the Office split is
# resolved at runtime from conditioned/total floor area.
# ---------------------------------------------------------------------------

# Global taxonomy (country != India)
GLOBAL_CATEGORY_TO_EPI = {
    ("Office", "Grade A"): ("Office", "by_ac", False),
    ("Office", "Grade B"): ("Office", "by_ac", False),
    ("Office", "Grade C"): ("Office", "by_ac", False),
    ("Hotels", "1 star"): ("Hotel", "Up to 3-star", False),
    ("Hotels", "2 star"): ("Hotel", "Up to 3-star", False),
    ("Hotels", "3 star"): ("Hotel", "Up to 3-star", False),
    ("Hotels", "4 star"): ("Hotel", "Above 3-star", False),
    ("Hotels", "5 star"): ("Hotel", "Above 3-star", False),
    ("Resorts", "1 star"): ("Hotel", "Up to 3-star", True),  # Hotel proxy
    ("Resorts", "2 star"): ("Hotel", "Up to 3-star", True),
    ("Resorts", "3 star"): ("Hotel", "Up to 3-star", True),
    ("Resorts", "4 star"): ("Hotel", "Up to 3-star", True),
    ("Resorts", "5 star"): ("Hotel", "Up to 3-star", True),
    ("Retail", "Shopping Mall"): ("Shopping Mall", None, False),
    ("Retail", "Supermarket"): ("Shopping Mall", None, False),
    ("Retail", "Department Store"): ("Shopping Mall", None, False),
    ("Retail", "Small Food Retail"): ("Shopping Mall", None, False),
    ("Retail", "Non-food Big Box Retail"): ("Shopping Mall", None, False),
    ("Healthcare", "Private Hospital"): ("Hospital", None, False),
    ("Healthcare", "Public Hospital"): ("Hospital", None, False),
    ("Healthcare", "Multi-specialty Hospital"): ("Hospital", None, False),
    ("Healthcare", "Teaching Hospital"): ("Hospital", None, False),
    ("Healthcare", "Eye Hospital"): ("Hospital", None, False),
    ("Healthcare", "Dental Hospital"): ("Hospital", None, False),
    ("Healthcare", "Clinics"): ("Hospital", None, False),
    ("Healthcare", "Diagnostic Center"): ("Hospital", None, False),
    ("Healthcare", "Nursing Homes"): ("Hospital", None, False),
    ("Education", "Preschool"): ("Institute", None, False),
    ("Education", "School"): ("Institute", None, False),
    ("Education", "University"): ("Institute", None, False),
    ("Education", "Sports Facilities"): ("Institute", None, False),
    ("Education", "Other Educational Facilities"): ("Institute", None, False),
    ("Homes", "Low income"): ("Residential", None, False),
    ("Homes", "Middle income"): ("Residential", None, False),
    ("Homes", "High income"): ("Residential", None, False),
    ("Apartments", "Low income"): ("Residential", None, False),
    ("Apartments", "Middle income"): ("Residential", None, False),
    ("Apartments", "High income"): ("Residential", None, False),
    ("Apartments", "Serviced apartment"): ("Residential", None, False),
    # Industrial / Mixed Use -> no EPI benchmark (Layer 1 hidden)
}

# Fall back to category-only mapping when the exact subcategory is not listed above.
GLOBAL_CATEGORY_ONLY_TO_EPI = {
    "Office": ("Office", "by_ac", False),
    "Hotels": ("Hotel", "Up to 3-star", False),
    "Resorts": ("Hotel", "Up to 3-star", True),
    "Retail": ("Shopping Mall", None, False),
    "Healthcare": ("Hospital", None, False),
    "Education": ("Institute", None, False),
    "Homes": ("Residential", None, False),
    "Apartments": ("Residential", None, False),
}

# India taxonomy (country == India)
INDIA_CATEGORY_TO_EPI = {
    ("Office/Business", "Day time use"): ("Office", "by_ac", False),
    ("Office/Business", "24-hour use"): ("Office", "by_ac", False),
    ("Hospitality", "No-star Hotels"): ("Hotel", "Up to 3-star", False),
    ("Hospitality", "Star Hotel"): ("Hotel", "Up to 3-star", True),  # spans 2-5 star
    ("Hospitality", "Resort"): ("Hotel", "Up to 3-star", True),  # Hotel proxy
    ("Shopping complex", "Shopping malls"): ("Shopping Mall", None, False),
    ("Shopping complex", "Stand-alone Retails"): ("Shopping Mall", None, False),
    ("Shopping complex", "Super Markets"): ("Shopping Mall", None, False),
    ("Shopping complex", "Open Gallery Malls"): ("Shopping Mall", None, False),
    ("Health care", "Hospital"): ("Hospital", None, False),
    ("Health care", "Out-patient Healthcare"): ("Hospital", None, False),
    ("Educational", "Schools"): ("Institute", None, False),
    ("Educational", "College"): ("Institute", None, False),
    ("Educational", "Universities"): ("Institute", None, False),
    ("Educational", "Training institutes"): ("Institute", None, False),
    ("Homes", "Low income"): ("Residential", None, False),
    ("Homes", "Middle income"): ("Residential", None, False),
    ("Homes", "High income"): ("Residential", None, False),
    ("Apartments", "Low income"): ("Residential", None, False),
    ("Apartments", "Middle income"): ("Residential", None, False),
    ("Apartments", "High income"): ("Residential", None, False),
    ("Apartments", "Serviced apartment"): ("Residential", None, False),
    # Assembly / Mixed-use building -> no EPI benchmark (Layer 1 hidden)
}

INDIA_CATEGORY_ONLY_TO_EPI = {
    "Office/Business": ("Office", "by_ac", False),
    "Hospitality": ("Hotel", "Up to 3-star", True),
    "Shopping complex": ("Shopping Mall", None, False),
    "Health care": ("Hospital", None, False),
    "Educational": ("Institute", None, False),
    "Homes": ("Residential", None, False),
    "Apartments": ("Residential", None, False),
}

# ---------------------------------------------------------------------------
# National-average EUI (kWh/m²/yr), from CONSOLIDATED National_Avg_EUI.
# Keyed by (country, EPI building_type, EPI sub_type, EPI climate label).
# sub_type of "-" is stored as None. Only non-blank cells are present, so a
# missing key => no national benchmark for that combination.
# ---------------------------------------------------------------------------

# Indonesia offices, added 19.10.2026 from a measured study rather than a code.
#
# No ALCBT country publishes a whole-building EUI in its building code - they
# are all prescriptive, setting envelope, lighting density and equipment
# minimums. A national average EUI is a measured statistic, which is why
# India's rows come from the BEE 1,160-building survey and not from ECSBC.
#
# Benchmarking Energy Use Intensity of 33 Office Buildings in Indonesia gives
# a mean of 160 kWh/m2/yr, with under 115 treated as high performance and over
# 190 as significantly inefficient. Entered against both climates Indonesia
# already has rows for, because the study reports one national mean and does
# not break down by climate - that is a limit of the source, not a choice.
# NOT APPLIED. The workbook carries 250 for an Indonesian office and this
# study measures 160 - a 56% gap on a figure that 586 production buildings are
# benchmarked against. Swapping it would make every Indonesian office look
# materially worse overnight, and the two numbers may not measure the same
# thing: the study covers 33 offices and does not say whether its EUI includes
# the same end uses. Recorded for a decision, not applied.
INDONESIA_OFFICE_EUI_MEASURED_2025 = 160.0
INDONESIA_OFFICE_EUI_IN_USE = 250.0

NATIONAL_AVG_EUI = {
    # --- Thailand: these figures are suspect, and unchanged -----------------
    #
    # Thailand's rows are not Indian copies - they are distinct, and carry two
    # decimal places, which suggests they were computed rather than surveyed.
    # But offices at 59.26 kWh/m2/yr is about a quarter of the 225 a study of
    # 41 Bangkok offices calls typical, and hotels at 179.67 against a
    # measured Thai average of 321.84.
    #
    # A figure four times out is more likely measuring something else -
    # electricity only, or per conditioned area rather than per gross floor
    # area - than simply wrong. Left alone until what it measures is known,
    # because swapping one unexplained number for another is not an
    # improvement. Recorded in docs/layer2_benchmark_sources.md.

    # --- Vietnam and Cambodia: India's rows were removed 19.10.2026 ---------
    #
    # 15 of Vietnam's 22 rows and 7 of Cambodia's 15 were India's BEE figures
    # copied verbatim, so a Vietnamese hotel was told its national average was
    # 333 kWh/m2/yr - India's warm-and-humid figure from a survey of 1,160
    # Indian buildings. Published Vietnamese research puts hotels at 151.
    #
    # Deleted rather than relabelled. An Indian benchmark is not a proxy for
    # Vietnam: different climate, construction, occupancy and grid. A gap is a
    # true statement about what has been published; a borrowed number is not,
    # and it is invisible precisely because it looks like data.
    #
    # What remains for each country is its own. Candidates for filling the
    # gaps, read in summary only and not yet adopted, are recorded in
    # docs/layer2_benchmark_sources.md.
    # --- Indonesia ---------------------------------------------------------
    #
    # Replaced 19.10.2026 from the national studies. The previous figures -
    # office 250, hotel 350, mall 450, hospital 450 - sat ABOVE the "wasteful"
    # threshold of every one of those studies, so almost any Indonesian
    # building scored well against its own national average. Residential at 60
    # was the opposite: little over half the measured average, so homes looked
    # bad.
    #
    # Sources, per row:
    #   C40 Cities (2023), Baseline Study on the Energy and Buildings
    #       Landscape of Jakarta - 150 buildings, publishes true averages.
    #   BPPT (2020), Benchmarking Specific Energy Consumption in the
    #       Commercial Building Sector - 110 buildings across 7 cities,
    #       publishes classification BANDS, not averages. Where a band is used
    #       the figure is the Efficient / Fairly-Efficient boundary, which is
    #       where the middle of the distribution sits. That is an
    #       interpretation of the source, not a number the source states, and
    #       it is recorded as such.
    #
    # One figure per type applies to every Indonesian climate. The studies are
    # national and Jakarta-weighted and do not resolve by climate zone, so a
    # per-climate figure would be invented. Writing one value to all zones is
    # what the data supports - and it matters: 252 of 430 Indonesian buildings
    # are in the composite zone, which previously had no row at all, so only
    # 15 of them found any benchmark.
    #
    # BPPT split offices at 5,000 m2 explicitly because "large office
    # buildings usually use centralized air conditioning systems, while
    # medium-sized offices rely on split units". That is the source's own
    # reasoning for mapping its size split onto BEAT's conditioned-area split.
    # Office / >50% AC: 155 - BPPT 2020 large office, E/FE boundary (centralised AC)
    ("Indonesia", "Office", ">50% AC", "Tropical Wet"): 155,
    ("Indonesia", "Office", ">50% AC", "Composite"): 155,
    ("Indonesia", "Office", ">50% AC", "Warm & Humid"): 155,
    ("Indonesia", "Office", ">50% AC", "Temperate"): 155,
    ("Indonesia", "Office", ">50% AC", "Hot & Dry"): 155,
    # Office / <50% AC: 158 - BPPT 2020 medium office, E/FE boundary (split units)
    ("Indonesia", "Office", "<50% AC", "Tropical Wet"): 158,
    ("Indonesia", "Office", "<50% AC", "Composite"): 158,
    ("Indonesia", "Office", "<50% AC", "Warm & Humid"): 158,
    ("Indonesia", "Office", "<50% AC", "Temperate"): 158,
    ("Indonesia", "Office", "<50% AC", "Hot & Dry"): 158,
    # Hotel / Up to 3-star: 170 - BPPT 2020 mean of budget 145 and 3-star 194
    ("Indonesia", "Hotel", "Up to 3-star", "Tropical Wet"): 170,
    ("Indonesia", "Hotel", "Up to 3-star", "Composite"): 170,
    ("Indonesia", "Hotel", "Up to 3-star", "Warm & Humid"): 170,
    ("Indonesia", "Hotel", "Up to 3-star", "Temperate"): 170,
    ("Indonesia", "Hotel", "Up to 3-star", "Hot & Dry"): 170,
    # Hotel / Above 3-star: 196 - BPPT 2020 mean of 4-star 199 and 5-star 193
    ("Indonesia", "Hotel", "Above 3-star", "Tropical Wet"): 196,
    ("Indonesia", "Hotel", "Above 3-star", "Composite"): 196,
    ("Indonesia", "Hotel", "Above 3-star", "Warm & Humid"): 196,
    ("Indonesia", "Hotel", "Above 3-star", "Temperate"): 196,
    ("Indonesia", "Hotel", "Above 3-star", "Hot & Dry"): 196,
    # Shopping Mall: 383 - C40 2023 Jakarta mall average
    ("Indonesia", "Shopping Mall", None, "Tropical Wet"): 383,
    ("Indonesia", "Shopping Mall", None, "Composite"): 383,
    ("Indonesia", "Shopping Mall", None, "Warm & Humid"): 383,
    ("Indonesia", "Shopping Mall", None, "Temperate"): 383,
    ("Indonesia", "Shopping Mall", None, "Hot & Dry"): 383,
    # Hospital: 214 - BPPT 2020 Class B, E/FE boundary
    ("Indonesia", "Hospital", None, "Tropical Wet"): 214,
    ("Indonesia", "Hospital", None, "Composite"): 214,
    ("Indonesia", "Hospital", None, "Warm & Humid"): 214,
    ("Indonesia", "Hospital", None, "Temperate"): 214,
    ("Indonesia", "Hospital", None, "Hot & Dry"): 214,
    # Residential: 108 - C40 2023 Jakarta residential average
    ("Indonesia", "Residential", None, "Tropical Wet"): 108,
    ("Indonesia", "Residential", None, "Composite"): 108,
    ("Indonesia", "Residential", None, "Warm & Humid"): 108,
    ("Indonesia", "Residential", None, "Temperate"): 108,
    ("Indonesia", "Residential", None, "Hot & Dry"): 108,
    # ---- Office <50% AC ----
    ("India", "Office", "<50% AC", "Warm & Humid"): 101,
    ("Thailand", "Office", "<50% AC", "Warm & Humid"): 59.26,
    ("India", "Office", "<50% AC", "Composite"): 86,
    ("Thailand", "Office", "<50% AC", "Composite"): 59.26,
    ("India", "Office", "<50% AC", "Hot & Dry"): 90,
    ("India", "Office", "<50% AC", "Temperate"): 94,
    ("Vietnam", "Office", "<50% AC", "Tropical Wet"): 150,
    ("Cambodia", "Office", "<50% AC", "Tropical Wet"): 250,
    ("Thailand", "Office", "<50% AC", "Tropical Wet"): 59.26,
    # ---- Office >50% AC ----
    ("India", "Office", ">50% AC", "Warm & Humid"): 182,
    ("Thailand", "Office", ">50% AC", "Warm & Humid"): 59.26,
    ("India", "Office", ">50% AC", "Composite"): 179,
    ("Thailand", "Office", ">50% AC", "Composite"): 59.26,
    ("India", "Office", ">50% AC", "Hot & Dry"): 173,
    # The BEE tables call this zone "Moderate"; every other row here was
    # normalised to BEAT's own "Temperate" and this one was missed, so a
    # temperate-zone Indian office with more than 50% conditioned area found
    # no benchmark at all. The figure is unchanged.
    ("India", "Office", ">50% AC", "Temperate"): 179,
    ("Vietnam", "Office", ">50% AC", "Moderate"): 179,
    ("Vietnam", "Office", ">50% AC", "Tropical Wet"): 150,
    ("Cambodia", "Office", ">50% AC", "Tropical Wet"): 250,
    ("Thailand", "Office", ">50% AC", "Tropical Wet"): 59.26,
    # ---- Hotel Up to 3-star ----
    ("India", "Hotel", "Up to 3-star", "Warm & Humid"): 215,
    ("Thailand", "Hotel", "Up to 3-star", "Warm & Humid"): 179.67,
    ("India", "Hotel", "Up to 3-star", "Composite"): 201,
    ("Thailand", "Hotel", "Up to 3-star", "Composite"): 179.67,
    ("India", "Hotel", "Up to 3-star", "Hot & Dry"): 167,
    ("India", "Hotel", "Up to 3-star", "Temperate"): 107,
    ("Vietnam", "Hotel", "Up to 3-star", "Tropical Wet"): 250,
    ("Cambodia", "Hotel", "Up to 3-star", "Tropical Wet"): 350,
    ("Thailand", "Hotel", "Up to 3-star", "Tropical Wet"): 179.67,
    # ---- Hotel Above 3-star ----
    ("India", "Hotel", "Above 3-star", "Warm & Humid"): 333,
    ("Cambodia", "Hotel", "Above 3-star", "Warm & Humid"): 290,
    ("Thailand", "Hotel", "Above 3-star", "Warm & Humid"): 179.67,
    ("India", "Hotel", "Above 3-star", "Composite"): 290,
    ("Thailand", "Hotel", "Above 3-star", "Composite"): 179.67,
    ("India", "Hotel", "Above 3-star", "Hot & Dry"): 250,
    ("India", "Hotel", "Above 3-star", "Temperate"): 313,
    ("Vietnam", "Hotel", "Above 3-star", "Tropical Wet"): 250,
    ("Cambodia", "Hotel", "Above 3-star", "Tropical Wet"): 350,
    ("Thailand", "Hotel", "Above 3-star", "Tropical Wet"): 179.67,
    # ---- Shopping Mall ----
    ("India", "Shopping Mall", None, "Warm & Humid"): 428,
    ("Thailand", "Shopping Mall", None, "Warm & Humid"): 150.81,
    ("India", "Shopping Mall", None, "Composite"): 327,
    ("Thailand", "Shopping Mall", None, "Composite"): 150.81,
    ("India", "Shopping Mall", None, "Hot & Dry"): 273,
    ("India", "Shopping Mall", None, "Temperate"): 257,
    ("Vietnam", "Shopping Mall", None, "Tropical Wet"): 300,
    ("Cambodia", "Shopping Mall", None, "Tropical Wet"): 450,
    ("Thailand", "Shopping Mall", None, "Tropical Wet"): 150.81,
    # ---- Hospital ----
    ("India", "Hospital", None, "Warm & Humid"): 275,
    ("Cambodia", "Hospital", None, "Warm & Humid"): 264,
    ("Thailand", "Hospital", None, "Warm & Humid"): 171.03,
    ("India", "Hospital", None, "Composite"): 264,
    ("Thailand", "Hospital", None, "Composite"): 171.03,
    ("India", "Hospital", None, "Hot & Dry"): 261,
    ("India", "Hospital", None, "Temperate"): 247,
    ("Vietnam", "Hospital", None, "Tropical Wet"): 300,
    ("Cambodia", "Hospital", None, "Tropical Wet"): 450,
    # ---- Institute ----
    ("India", "Institute", None, "Warm & Humid"): 150,
    ("India", "Institute", None, "Composite"): 117,
    ("India", "Institute", None, "Hot & Dry"): 106,
    ("India", "Institute", None, "Temperate"): 129,
    # ---- BPO (India only) ----
    ("India", "BPO", None, "Warm & Humid"): 452,
    ("India", "BPO", None, "Composite"): 437,
    ("India", "BPO", None, "Temperate"): 433,
    # ---- Residential ----
    ("India", "Residential", None, "Warm & Humid"): 64,
    ("India", "Residential", None, "Composite"): 60,
    ("India", "Residential", None, "Hot & Dry"): 67,
    ("India", "Residential", None, "Temperate"): 31,
}

# ---------------------------------------------------------------------------
# India best-practice EUI (national EPI x (1 - Super-ECBC%)), pre-computed from
# CONSOLIDATED BestPractice_India. Keyed like NATIONAL_AVG_EUI but without country
# (India only). Rows with no ECBC tier (Office Moderate, Residential) are absent
# -> best practice unavailable, national-average line only.
# ---------------------------------------------------------------------------

BEST_PRACTICE_INDIA = {
    ("Office", "<50% AC", "Warm & Humid"): 76.8,
    ("Office", "<50% AC", "Composite"): 67.1,
    ("Office", "<50% AC", "Hot & Dry"): 70.2,
    ("Office", "<50% AC", "Temperate"): 70.5,
    ("Office", ">50% AC", "Warm & Humid"): 138.3,
    ("Office", ">50% AC", "Composite"): 139.6,
    ("Office", ">50% AC", "Hot & Dry"): 134.9,
    ("Hotel", "Up to 3-star", "Warm & Humid"): 174.2,
    ("Hotel", "Up to 3-star", "Composite"): 162.8,
    ("Hotel", "Up to 3-star", "Hot & Dry"): 135.3,
    ("Hotel", "Up to 3-star", "Temperate"): 85.6,
    ("Hotel", "Above 3-star", "Warm & Humid"): 269.7,
    ("Hotel", "Above 3-star", "Composite"): 234.9,
    ("Hotel", "Above 3-star", "Hot & Dry"): 202.5,
    ("Hotel", "Above 3-star", "Temperate"): 250.4,
    ("Shopping Mall", None, "Warm & Humid"): 308.2,
    ("Shopping Mall", None, "Composite"): 242.0,
    ("Shopping Mall", None, "Hot & Dry"): 196.6,
    ("Shopping Mall", None, "Temperate"): 182.5,
    ("Hospital", None, "Warm & Humid"): 211.8,
    ("Hospital", None, "Composite"): 203.3,
    ("Hospital", None, "Hot & Dry"): 198.4,
    ("Hospital", None, "Temperate"): 180.3,
    ("Institute", None, "Warm & Humid"): 99.0,
    ("Institute", None, "Composite"): 77.2,
    ("Institute", None, "Hot & Dry"): 70.0,
    ("Institute", None, "Temperate"): 85.1,
    ("BPO", None, "Warm & Humid"): 343.5,
    ("BPO", None, "Composite"): 332.1,
    ("BPO", None, "Temperate"): 320.4,
}

# ---------------------------------------------------------------------------
# Non-India LEED whole-building best-practice EUI (kWh/m²/yr) by EPI type
# (CONSOLIDATED BestPractice_NonIndia). Institute/BPO have no LEED value ->
# best practice unavailable, national-average line only. Applied with a guard:
# shown only where LEED < national EPI for the building's climate.
# ---------------------------------------------------------------------------

LEED_BEST_PRACTICE = {
    "Office": 136,
    "Hotel": 157,
    "Shopping Mall": 267,
    "Hospital": 447,
    "Residential": 111,
}

# ---------------------------------------------------------------------------
# Grid emission factor fallback (kgCO2/kWh), corrected 2026-07 (CONSOLIDATED
# Grid_EF). Used ONLY when no electricity EPD is entered — the primary factor is
# derived at runtime from the electricity EPD (building_stats._derive_grid_emission_factor).
# ---------------------------------------------------------------------------

GRID_EF_FALLBACK = {
    "India": 0.7051,
    "Indonesia": 0.78,
    "Vietnam": 0.659,
    "Thailand": 0.475,
    "Cambodia": 0.588,
}

BENCHMARK_COUNTRIES = set(GRID_EF_FALLBACK.keys())


# ---------------------------------------------------------------------------
# Building -> EPI benchmark resolution
# ---------------------------------------------------------------------------

def _resolve_epi_type(building):
    """Map the building's category/subcategory to (epi_type, epi_sub_type, approx).

    Returns None if the category has no EPI benchmark (Industrial, Mixed Use, etc.)
    or if the building has no category.
    """
    try:
        cat = building.category.category.name if building.category and building.category.category else None
        sub = building.category.subcategory.name if building.category and building.category.subcategory else None
    except AttributeError:
        return None
    if not cat:
        return None

    country_name = (building.country.name or "") if building.country else ""
    is_india = country_name.strip().lower() == "india"

    exact_map = INDIA_CATEGORY_TO_EPI if is_india else GLOBAL_CATEGORY_TO_EPI
    only_map = INDIA_CATEGORY_ONLY_TO_EPI if is_india else GLOBAL_CATEGORY_ONLY_TO_EPI

    if sub and (cat, sub) in exact_map:
        return exact_map[(cat, sub)]
    if cat in only_map:
        return only_map[cat]
    return None


def _resolve_office_ac_subtype(building):
    """Office EPI sub-type from conditioned/total floor area (>=50% => '>50% AC').

    Missing conditioned area defaults to '>50% AC' with an approximation flag
    (typical commercial case, spec §10).
    """
    try:
        total = float(building.total_floor_area) if building.total_floor_area else 0.0
        cond = float(building.cond_floor_area) if building.cond_floor_area else None
    except (AttributeError, TypeError, ValueError):
        total, cond = 0.0, None
    if cond is None or total <= 0:
        return ">50% AC", True
    return (">50% AC" if (cond / total) >= 0.5 else "<50% AC"), False


def get_operational_benchmark_for_building(building):
    """Resolve the Layer-1 EPI benchmark entry for a building.

    Returns a dict with national_average, best_practice (or None), and metadata,
    or None when no benchmark applies (unsupported country/category, or a blank
    benchmark cell — Layer 1 is then hidden).
    """
    country_name = (building.country.name or "").strip() if building.country else ""
    if country_name not in BENCHMARK_COUNTRIES:
        return None

    epi = _resolve_epi_type(building)
    if epi is None:
        return None
    epi_type, epi_sub, type_approx = epi

    # Climate label + approximation flag
    climate_slug = (building.climate_zone.name or "").strip().lower() if building.climate_zone else ""
    climate_label, climate_approx = CLIMATE_TO_EPI_LABEL.get(climate_slug, (None, False))
    if not climate_label:
        return None

    # Office AC split
    ac_approx = False
    if epi_sub == "by_ac":
        epi_sub, ac_approx = _resolve_office_ac_subtype(building)

    national = NATIONAL_AVG_EUI.get((country_name, epi_type, epi_sub, climate_label))
    if national is None:
        return None

    is_india = country_name.lower() == "india"
    if is_india:
        best = BEST_PRACTICE_INDIA.get((epi_type, epi_sub, climate_label))
    else:
        best = LEED_BEST_PRACTICE.get(epi_type)

    # Guard: best practice shown only when it is below the national average.
    if best is not None and best >= national:
        best = None

    return {
        "country": country_name,
        "building_type": epi_type,
        "sub_type": epi_sub,
        "climate_label": climate_label,
        "national_average_eui": float(national),
        "best_practice_eui": float(best) if best is not None else None,
        "is_approximation": bool(type_approx or climate_approx or ac_approx),
    }


# ---------------------------------------------------------------------------
# Benchmark position calculation (carbon domain)
# ---------------------------------------------------------------------------

def calculate_operational_benchmark_position(actual_eui, benchmark_entry, grid_factor,
                                             floor_area, reference_period=50):
    """Place the building on the operational EUI/carbon benchmark scale.

    Args:
        actual_eui:        building's actual EUI (kWh/m²/yr)
        benchmark_entry:   dict from get_operational_benchmark_for_building()
        grid_factor:       kgCO2eq/kWh (from electricity EPD or fallback)
        floor_area:        gross floor area (m²)
        reference_period:  years, for lifetime figures (default 50)

    Returns a dict for the template, or None if inputs are insufficient.
    All carbon figures are kgCO2eq/m²/yr unless suffixed.
    """
    if not benchmark_entry or actual_eui is None or grid_factor is None:
        return None
    try:
        actual_eui = float(actual_eui)
        grid = float(grid_factor)
        gfa = float(floor_area) if floor_area else 0.0
        period = int(reference_period) if reference_period else 50
    except (TypeError, ValueError):
        return None
    if grid <= 0:
        return None

    national_eui = benchmark_entry["national_average_eui"]
    best_eui = benchmark_entry["best_practice_eui"]

    actual_carbon = actual_eui * grid
    national_carbon = national_eui * grid
    best_carbon = best_eui * grid if best_eui is not None else None

    result = {
        "actual_eui": round(actual_eui, 1),
        "actual_carbon": round(actual_carbon, 1),
        "national_average_eui": round(national_eui, 1),
        "national_average": round(national_carbon, 1),
        "best_practice_eui": round(best_eui, 1) if best_eui is not None else None,
        "best_practice": round(best_carbon, 1) if best_carbon is not None else None,
        "grid_factor": round(grid, 4),
        "building_type": benchmark_entry["building_type"],
        "sub_type": benchmark_entry["sub_type"],
        "climate_label": benchmark_entry["climate_label"],
        "is_approximation": benchmark_entry["is_approximation"],
        "has_best_practice": best_carbon is not None,
    }

    # Tier + position (spec §10). When best practice is unavailable, show the
    # national-average marker only, with no range-based tier.
    if best_carbon is not None and national_carbon > best_carbon:
        scale = national_carbon - best_carbon
        raw = (actual_carbon - best_carbon) / scale * 100
        position_pct = max(0.0, min(100.0, raw))
        result["position_pct"] = round(position_pct, 1)
        result["better_than_pct"] = round(max(0.0, min(100.0, 100 - position_pct)))
        if actual_carbon <= best_carbon:
            result["tier"] = "Exceeds best practice"
        elif actual_carbon <= national_carbon:
            result["tier"] = "Between best practice and national average"
        else:
            result["tier"] = "Above national average"
    else:
        result["position_pct"] = None
        result["better_than_pct"] = None
        result["tier"] = (
            "Above national average" if actual_carbon > national_carbon
            else "At or below national average"
        )

    # Gap saving vs. best practice (only when actual is above best practice).
    if best_eui is not None and actual_eui > best_eui:
        gap_eui = actual_eui - best_eui
        result["gap_carbon_per_year"] = round(gap_eui * grid, 1)
        result["gap_energy_kwh"] = round(gap_eui * gfa) if gfa > 0 else 0
        result["gap_carbon_lifetime"] = round(gap_eui * grid * period)
    else:
        result["gap_carbon_per_year"] = 0.0
        result["gap_energy_kwh"] = 0
        result["gap_carbon_lifetime"] = 0

    return result
