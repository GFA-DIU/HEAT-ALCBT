"""GCCA concrete Low Carbon Rating (A–G) — computed dynamically from an EPD's
GWP (A1–A3, per m³) and its compressive strength class.

Scheme: GCCA "Global Reference Thresholds" (https://gccaepd.org/blog/lcr).
Bands are keyed to the concrete's CYLINDER strength class (Mxx). Thresholds are
the upper bound (kgCO₂e/m³) of each band; lower GWP = better letter.

This rates READY-MIX / PRECAST STRUCTURAL CONCRETE only (declared per m³, with a
strength class). It does NOT apply to cement, AAC, mortar, grout, primers, etc.

Strength inputs handled:
  - Thai ready-mix grade in KSC (kg/cm², CUBE strength): KSC → cube MPa (×0.0980665)
    → nearest EN-206 class → that class's cylinder Mxx.
  - EN-206 class "C20/25" (cylinder/cube).
  - Explicit "M30" / cylinder MPa.

Grades outside the GCCA columns (M20/25/30/35/40/50) — e.g. M16 (Thai 180/210 KSC)
or M45 — return None (left unrated), per the agreed "skip off-table" rule.
"""
import re

KSC_TO_MPA = 0.0980665  # 1 kg/cm² in MPa

# GCCA "top of band" thresholds, kgCO₂e/m³, per cylinder strength class.
# Order = [A, B, C, D, E, F]; anything above F is G.
GCCA_THRESHOLDS = {
    20: [68, 115, 161, 208, 255, 302],
    25: [75, 127, 179, 231, 283, 335],
    30: [83, 141, 199, 256, 314, 372],
    35: [94, 159, 224, 288, 353, 418],
    40: [101, 171, 241, 310, 380, 450],
    50: [113, 190, 268, 345, 422, 500],
}
GCCA_COLUMNS = set(GCCA_THRESHOLDS)  # {20,25,30,35,40,50}

# EN-206 characteristic CUBE strength (MPa) -> CYLINDER class Mxx.
_EN206_CUBE_TO_CYL = {10: 8, 15: 12, 20: 16, 25: 20, 30: 25, 37: 30, 45: 35, 50: 40, 55: 45, 60: 50}

_KSC_RE = re.compile(r"(\d+)\s*(?:-\s*(\d+))?\s*KSC", re.IGNORECASE)
_EN206_RE = re.compile(r"\bC\s?(\d{2})\s*/\s*(\d{2})\b")
_MXX_RE = re.compile(r"\bM\s?(\d{2,3})\b")


def _cube_mpa_to_mxx(cube_mpa):
    """Nearest EN-206 class by cube strength -> its cylinder Mxx (or None if off-table)."""
    nearest_cube = min(_EN206_CUBE_TO_CYL, key=lambda c: abs(c - cube_mpa))
    mxx = _EN206_CUBE_TO_CYL[nearest_cube]
    return mxx if mxx in GCCA_COLUMNS else None


def strength_to_mxx(name):
    """Parse a compressive strength class from an EPD name -> GCCA cylinder Mxx.

    Returns an int in GCCA_COLUMNS, or None if not parseable / off-table / a range.
    """
    if not name:
        return None
    # Thai KSC (cube). A range (e.g. "200-300 KSC") is ambiguous -> skip.
    m = _KSC_RE.search(name)
    if m:
        if m.group(2):
            return None  # range -> cannot assign one class
        return _cube_mpa_to_mxx(int(m.group(1)) * KSC_TO_MPA)
    # EN-206 "C20/25" -> use the cube (second) value.
    m = _EN206_RE.search(name)
    if m:
        return _cube_mpa_to_mxx(int(m.group(2)))
    # Explicit "M30" (already cylinder).
    m = _MXX_RE.search(name)
    if m:
        v = int(m.group(1))
        return v if v in GCCA_COLUMNS else None
    return None


def rate(gwp_per_m3, mxx):
    """Return the A–G band for a per-m³ GWP at cylinder class Mxx, or None."""
    if mxx not in GCCA_THRESHOLDS or gwp_per_m3 is None:
        return None
    for letter, thr in zip("ABCDEF", GCCA_THRESHOLDS[mxx]):
        if gwp_per_m3 <= thr:
            return letter
    return "G"
