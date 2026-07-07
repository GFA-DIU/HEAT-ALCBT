"""
Geo-based auto-population of climate type and seismic zone.

Implements BEAT-DEV spec: "Auto-populate Climate Type and Seismic Zone
from Building Location" v1.0.

GeoJSON files required (place in pages/data/geo/):
  koppen_geiger.geojson         — Beck et al. (2018), column: climate_code
  india_composite_zone.geojson  — NBC/ECBC states, column: zone = 'composite'
  india_seismic_zones_IS1893.geojson — IS 1893:2016, column: zone ('Zone II'–'Zone V')
  sea_seismic_zones_psha.geojson     — PSHA-based, column: zone ('Low'/'Moderate'/'High'/'Very High')

All files must use EPSG:4326 (WGS84).
"""

import logging
import os

import pandas as pd

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Köppen code → BEAT climate type mapping
# Source: BEAT Developer Specification v1.0, Section 4.2
# ---------------------------------------------------------------------------

KOPPEN_TO_BEAT = {
    # Tropical-wet
    "Af": "tropical-wet",
    "Am": "tropical-wet",
    "Aw": "tropical-wet",
    "As": "tropical-wet",
    # Warm-humid
    "Cfa": "warm-humid",
    "Cwa": "warm-humid",
    "Csa": "warm-humid",
    "Cfb": "warm-humid",
    "Cfc": "warm-humid",
    # Hot-dry
    "BWh": "hot-dry",
    "BWk": "hot-dry",
    "BSh": "hot-dry",
    "BSk": "hot-dry",
    # Temperate
    "Cwb": "temperate",
    "Csb": "temperate",
    "Dsb": "temperate",
    "Dsc": "temperate",
    "Dfb": "temperate",
    "Dfc": "temperate",
    # Cold
    "Dfa": "cold",
    "Dwa": "cold",
    "Dwb": "cold",
    "Dwc": "cold",
    "Dwd": "cold",
    "Dfd": "cold",
    "ET":  "cold",
    "EF":  "cold",
}

# ---------------------------------------------------------------------------
# GeoJSON dataset paths
# ---------------------------------------------------------------------------

_DATA_DIR = os.path.join(os.path.dirname(__file__), "data", "geo")

_KOPPEN_PATH          = os.path.join(_DATA_DIR, "koppen_geiger.geojson")
_INDIA_COMPOSITE_PATH = os.path.join(_DATA_DIR, "india_composite_zone.geojson")
_INDIA_SEISMIC_PATH   = os.path.join(_DATA_DIR, "india_seismic_zones_IS1893.geojson")
_SEA_SEISMIC_PATH     = os.path.join(_DATA_DIR, "sea_seismic_zones_psha.geojson")

# ---------------------------------------------------------------------------
# Module-level cache — loaded once at first use
# ---------------------------------------------------------------------------

_koppen_zones    = None
_composite_zones = None
_india_seismic   = None
_sea_seismic     = None
_loaded          = False
_load_error      = None


def _load_datasets():
    """Load all GeoJSON datasets into module-level variables (once)."""
    global _koppen_zones, _composite_zones, _india_seismic, _sea_seismic
    global _loaded, _load_error

    if _loaded:
        return

    try:
        import geopandas as gpd

        missing = [p for p in (
            _KOPPEN_PATH, _INDIA_COMPOSITE_PATH,
            _INDIA_SEISMIC_PATH, _SEA_SEISMIC_PATH,
        ) if not os.path.exists(p)]

        if missing:
            _load_error = f"Missing GeoJSON files: {', '.join(missing)}"
            logger.warning("[geo_lookup] %s", _load_error)
            _loaded = True
            return

        _koppen_zones    = gpd.read_file(_KOPPEN_PATH)
        _composite_zones = gpd.read_file(_INDIA_COMPOSITE_PATH)
        _india_seismic   = gpd.read_file(_INDIA_SEISMIC_PATH)
        _sea_seismic     = gpd.read_file(_SEA_SEISMIC_PATH)

        logger.info("[geo_lookup] GeoJSON datasets loaded successfully.")

    except ImportError:
        _load_error = "geopandas is not installed. Run: pip install geopandas rtree"
        logger.warning("[geo_lookup] %s", _load_error)
    except Exception as exc:
        _load_error = f"Failed to load GeoJSON datasets: {exc}"
        logger.exception("[geo_lookup] %s", _load_error)
    finally:
        _loaded = True


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _get_beat_climate_type(koppen_code):
    """Map a Köppen code to a BEAT climate type. Falls back to 2-char prefix."""
    if not koppen_code:
        return None
    return (
        KOPPEN_TO_BEAT.get(koppen_code)
        or KOPPEN_TO_BEAT.get(koppen_code[:2])
    )


# ---------------------------------------------------------------------------
# Public resolvers
# ---------------------------------------------------------------------------

def resolve_climate_type(lat, lon, country):
    """
    Return (beat_climate_type, warning_message_or_None).

    beat_climate_type is one of: tropical-wet, warm-humid, hot-dry,
    temperate, cold, composite — or None if lookup failed.

    country should be the country name string (e.g. 'India').
    """
    _load_datasets()

    if _load_error or _koppen_zones is None:
        return None, "Climate type could not be determined. Please select manually."

    try:
        from shapely.geometry import Point
        import geopandas as gpd

        point_gdf = gpd.GeoDataFrame(
            geometry=[Point(lon, lat)],
            crs="EPSG:4326",
        )

        result = gpd.sjoin(point_gdf, _koppen_zones, how="left", predicate="within")
        koppen_code = result.iloc[0].get("climate_code") if not result.empty else None
        if pd.isna(koppen_code):
            return None, "Climate type could not be determined. Please select manually."

        beat_type = _get_beat_climate_type(koppen_code)

        if beat_type is None:
            return None, "Climate type not mapped. Please select manually."

        # India composite override
        if country == "India" and _composite_zones is not None:
            comp = gpd.sjoin(point_gdf, _composite_zones, how="left", predicate="within")
            comp_zone = comp.iloc[0].get("zone") if not comp.empty else None
            if not pd.isna(comp_zone) and str(comp_zone).lower() == "composite":
                beat_type = "composite"
                warning = (
                    "India has a country-specific composite climate zone (NBC/ECBC). "
                    "Please verify the auto-detected value before proceeding."
                )
                return beat_type, warning

        return beat_type, None

    except Exception as exc:
        logger.exception("[geo_lookup] resolve_climate_type failed: %s", exc)
        return None, "Climate type could not be determined. Please select manually."


def resolve_seismic_zone(lat, lon, country):
    """
    Return (seismic_zone_value, warning_message_or_None).

    For India: 'Zone II' | 'Zone III' | 'Zone IV' | 'Zone V'
    For others: 'Low' | 'Moderate' | 'High' | 'Very High'

    country should be the country name string (e.g. 'India').
    """
    _load_datasets()

    india_dataset = _india_seismic
    sea_dataset   = _sea_seismic

    if country == "India" and india_dataset is None:
        return None, "Seismic zone could not be determined. Please select manually."
    if country != "India" and sea_dataset is None:
        return None, "Seismic zone could not be determined. Please select manually."

    try:
        from shapely.geometry import Point
        import geopandas as gpd

        point_gdf = gpd.GeoDataFrame(
            geometry=[Point(lon, lat)],
            crs="EPSG:4326",
        )

        dataset = india_dataset if country == "India" else sea_dataset
        result = gpd.sjoin(point_gdf, dataset, how="left", predicate="within")

        zone = result.iloc[0].get("zone") if not result.empty else None
        if pd.isna(zone):
            return None, "Seismic zone could not be determined. Please select manually."

        return zone, None

    except Exception as exc:
        logger.exception("[geo_lookup] resolve_seismic_zone failed: %s", exc)
        return None, "Seismic zone could not be determined. Please select manually."


def resolve_building_location_fields(lat, lon, country):
    """
    Resolve both climate type and seismic zone in one call.
    Called when the user confirms their OSM location selection.

    Returns:
        {
            'climate_type': str | None,
            'climate_warning': str | None,
            'seismic_zone': str | None,
            'seismic_warning': str | None,
        }
    """
    climate_type, climate_warning = resolve_climate_type(lat, lon, country)
    seismic_zone, seismic_warning = resolve_seismic_zone(lat, lon, country)

    return {
        "climate_type":    climate_type,
        "climate_warning": climate_warning,
        "seismic_zone":    seismic_zone,
        "seismic_warning": seismic_warning,
    }
