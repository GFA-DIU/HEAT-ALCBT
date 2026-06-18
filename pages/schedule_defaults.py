"""
Operating schedule defaults loaded from the Excel reference file.
Lookup by (country_name, building_type, building_sub_type) → {hrs, days, weeks}.
India rows use 'India'; all ALCBT countries (Cambodia, Indonesia, Thailand, Vietnam)
map to 'ALCBT (CAM/IDN/THA/VNM)'.
"""

import logging
import os
from functools import lru_cache

logger = logging.getLogger(__name__)

ALCBT_COUNTRIES = {"Cambodia", "Indonesia", "Thailand", "Vietnam"}

EXCEL_PATH = os.path.join(os.path.dirname(__file__), "..", "docs", "BEAT_Operating_Schedule_Defaults.xlsx")


@lru_cache(maxsize=1)
def _load_defaults():
    try:
        import openpyxl
        wb = openpyxl.load_workbook(EXCEL_PATH, data_only=True)
        ws = wb["Operating_Schedule_Defaults"]
        rows = {}
        for row in ws.iter_rows(min_row=2, values_only=True):
            country, btype, subtype, hrs, days, weeks = row[0], row[1], row[2], row[3], row[4], row[5]
            if not isinstance(hrs, (int, float)) or not isinstance(days, (int, float)) or not isinstance(weeks, (int, float)):
                continue
            key = (_norm(country), _norm(btype), _norm(subtype))
            rows[key] = {"hrs": int(hrs), "days": int(days), "weeks": int(weeks)}
        logger.info("Loaded %d operating schedule defaults", len(rows))
        return rows
    except Exception:
        logger.exception("Failed to load operating schedule defaults from Excel")
        return {}


def _norm(s):
    return (s or "").strip().lower()


def get_schedule_defaults(country_name, building_type, building_sub_type):
    """
    Return {hrs, days, weeks} for the given country/type/subtype, or None if not found.
    country_name: e.g. "India", "Cambodia", "Indonesia", "Thailand", "Vietnam"
    """
    defaults = _load_defaults()

    if country_name in ALCBT_COUNTRIES:
        country_key = "alcbt (cam/idn/tha/vnm)"
    elif country_name == "India":
        country_key = "india"
    else:
        country_key = _norm(country_name)

    btype = _norm(building_type)
    bsub = _norm(building_sub_type)

    # DB-to-Excel category name aliases (India and ALCBT)
    _ALIASES = {
        "office/business": "office",
        "health care": "healthcare",
        "educational": "education",
        "shopping complex": "shopping complex",
        "industry / factory": "industry / factory",
        # ALCBT
        "office": "office buildings",
        "office buildings": "office buildings",
        "retail": "retail buildings",
        "retail buildings": "retail buildings",
        "industrial": "industrial buildings",
        "industry": "industrial buildings",
        "mixed use": "mixed-used building",
        "mixed-use building": "mixed-used building",
        "mixed-used building": "mixed-used building",
    }

    # Exact match first
    result = defaults.get((country_key, btype, bsub))
    if result:
        return result

    # Try alias mapping for both India and ALCBT
    btype_mapped = _ALIASES.get(btype, btype)
    if btype_mapped != btype:
        result = defaults.get((country_key, btype_mapped, bsub))
        if result:
            return result

    # For ALCBT: Excel sub-type often includes the category prefix + en-dash + star rating.
    # DB sub-types are just "1 star", "2 star", etc. Try prefixing.
    if country_key == "alcbt (cam/idn/tha/vnm)":
        # Try "hotels – N star" style (any separator between prefix and value)
        for key, val in defaults.items():
            if key[0] != country_key or key[1] != btype:
                continue
            # Check if sub key ends with our bsub (covers "hotels ? 3 star" when bsub="3 star")
            if key[2].endswith(bsub):
                return val

        # Try matching Excel category names to DB category names
        # e.g. DB "Office" → Excel "office buildings"
        _CATEGORY_ALIASES = {
            "office": "office buildings",
            "office buildings": "office buildings",
            "office/business": "office buildings",
            "retail": "retail buildings",
            "retail buildings": "retail buildings",
            "industry / factory": "industrial buildings",
            "industrial": "industrial buildings",
            "industry": "industrial buildings",
            "healthcare": "healthcare",
            "health care": "healthcare",
            "education": "education",
            "educational": "education",
            "mixed use": "mixed-used building",
            "mixed-use building": "mixed-used building",
            "mixed-used building": "mixed-used building",
        }
        btype_excel = _CATEGORY_ALIASES.get(btype, btype)
        for cat_to_try in ({btype, btype_excel}):
            result = defaults.get((country_key, cat_to_try, bsub))
            if result:
                return result
            # Suffix match: "3 star" matches "hotels – 3 star"; "Grade A" matches "grade a office"
            for key, val in defaults.items():
                if key[0] != country_key or key[1] != cat_to_try:
                    continue
                if key[2].endswith(bsub) or key[2].startswith(bsub):
                    return val

    return None
