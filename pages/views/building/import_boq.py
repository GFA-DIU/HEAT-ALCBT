"""Import a mapped BoQ (Bill of Quantities) as a building's structural components.

Lightweight, component-level counterpart to the whole-building importer. The user
supplies minimal building info (name, country, GFA) and uploads a BoQ in BEAT's
mapped format (the columns produced by our BoQ mapper):

    Work Description | Category | Unit | Quantity | BEAT Building Part |
    BEAT Building Component | BEAT Materials - Country | BEAT Materials

Each row becomes one material of a single **BoQ assembly** (is_boq=True) — exactly
the structure the add-BoQ modal creates — so the EXISTING carbon calc handles it
(the material's unit drives its dimension; the quantity is the raw amount). This
module only creates valid records; it never computes carbon or edits any formula.

Flow: parse_boq_rows -> resolve_boq_rows (match EPD + component) -> the caller shows
a preview of unmatched rows -> create_building_from_boq.
"""

import re
from decimal import Decimal

from django.db import transaction

from pages.models.assembly import (Assembly, AssemblyCategory,
                                    AssemblyCategoryTechnique, AssemblyDimension,
                                    AssemblyMode, StructuralProduct)
from pages.models.building import Building, BuildingAssembly
from pages.models.epd import Unit
from pages.views.building.import_building import _lookup_structural_epd, _resolve_country

# BoQ unit text -> BEAT Unit. Count-like units (set/nos/lot) collapse to pcs.
BOQ_UNIT_MAP = {
    "m3": Unit.M3, "m³": Unit.M3, "kg": Unit.KG, "m2": Unit.M2, "m²": Unit.M2,
    "m": Unit.M, "pcs": Unit.PCS, "nos": Unit.PCS, "no": Unit.PCS, "set": Unit.PCS,
    "lot": Unit.PCS, "ton": Unit.TON, "t": Unit.TON,
}

# Column header -> canonical field. Robust to the mapped-file layout and user edits.
_HEADER_ALIASES = {
    "description": ("work description", "description"),
    "unit": ("unit", "units"),
    "quantity": ("quantity", "vol", "volume", "qty"),
    "component": ("beat building component", "building component", "component"),
    "country": ("beat materials - country", "material country", "country"),
    "epd": ("beat materials", "material (epd)", "material", "epd", "epd name"),
}


def _norm(s):
    return re.sub(r"\s+", " ", str(s if s is not None else "").strip().lower())


def parse_boq_rows(grid):
    """grid: list of rows (each a list of cell values). Returns (rows, error).

    Finds the header row by name, then extracts item rows (a row is an item when it
    has a Material/EPD value and a recognised unit). Section headers / blanks skipped.
    """
    header_idx = None
    colmap = {}
    for i, row in enumerate(grid):
        vals = [_norm(c) for c in row]
        has_epd_hdr = any(v in _HEADER_ALIASES["epd"] for v in vals)
        has_desc_hdr = any(v in _HEADER_ALIASES["description"] for v in vals)
        if has_epd_hdr and has_desc_hdr:
            header_idx = i
            for j, v in enumerate(vals):
                for key, aliases in _HEADER_ALIASES.items():
                    if v in aliases and key not in colmap:
                        colmap[key] = j
            break
    if header_idx is None or "epd" not in colmap or "unit" not in colmap or "quantity" not in colmap:
        return [], ("Could not find the BoQ header. The sheet needs columns "
                    "'Work Description', 'Unit', 'Quantity' and 'BEAT Materials'.")

    rows = []
    for i in range(header_idx + 1, len(grid)):
        row = grid[i]

        def cell(key):
            j = colmap.get(key)
            return row[j] if (j is not None and j < len(row)) else None

        epd_name = str(cell("epd") or "").strip()
        unit_raw = _norm(cell("unit"))
        if not epd_name or unit_raw not in BOQ_UNIT_MAP:
            continue  # section header / non-item / unmapped unit
        try:
            qty = float(cell("quantity"))
        except (TypeError, ValueError):
            continue
        if qty <= 0:
            continue
        rows.append({
            "row": i + 1,
            "description": str(cell("description") or "").strip(),
            "component": str(cell("component") or "").strip(),
            "unit_raw": unit_raw,
            "unit": BOQ_UNIT_MAP[unit_raw],
            "quantity": qty,
            "country": str(cell("country") or "").strip(),
            "epd_name": epd_name,
        })
    return rows, None


def resolve_boq_rows(rows):
    """Attach the resolved EPD + AssemblyCategory + status to each row.

    Sets on each row:
      r['epd'] / r['epd_error'], r['category'],
      r['status'] in {'ok', 'no_epd', 'bad_unit'}, r['reason'] (for flagged rows).

    'bad_unit' = the EPD exists but can't be expressed in the BoQ's unit (no
    conversion), e.g. a precast-concrete EPD used per linear metre. These are the
    rows the preview asks the user to fix (pick another EPD/unit, or exclude).

    Returns (ready, flagged) where ready = status 'ok', flagged = the rest.
    """
    for r in rows:
        epd, err = _lookup_structural_epd(r["epd_name"], r["country"])
        r["epd"] = epd
        r["epd_error"] = err
        r["category"] = (
            AssemblyCategory.objects.filter(name__iexact=r["component"].strip()).first()
            if r["component"] else None
        )
        if not epd:
            r["status"] = "no_epd"
            r["reason"] = err or f"No EPD found for '{r['epd_name']}' ({r['country']})."
        else:
            avail = {str(u) for u in (epd.get_available_units() or {epd.declared_unit})}
            if str(r["unit"]) in avail:
                r["status"] = "ok"
                r["reason"] = ""
            else:
                r["status"] = "bad_unit"
                r["reason"] = (f"'{r['epd_name']}' cannot be used in "
                               f"'{r['unit_raw']}' (supports: {', '.join(sorted(avail))}).")

    ready = [r for r in rows if r["status"] == "ok"]
    flagged = [r for r in rows if r["status"] != "ok"]
    return ready, flagged


@transaction.atomic
def create_building_from_boq(user, name, country_name, gfa, rows, building_type=None):
    """Create a building whose structural components come from resolved BoQ rows.

    `rows` must already carry a resolved r['epd'] (call resolve_boq_rows first;
    rows without an EPD are skipped). One BoQ assembly holds all materials.
    Returns the new Building. Operational data is left empty — the user completes
    it in the normal editor.
    """
    country = None
    if country_name:
        country, _ = _resolve_country(country_name)

    building = Building.objects.create(
        name=name,
        total_floor_area=Decimal(str(gfa)),
        created_by=user,
        country=country,
        category=building_type,          # optional CategorySubcategory
        reference_period=50,
        climate_zone=None,
    )

    assembly = Assembly.objects.create(
        created_by=user,
        name=f"{name} — BoQ",
        dimension=AssemblyDimension.AREA,   # placeholder; BoQ dimension is per-material (from unit)
        mode=AssemblyMode.CUSTOM,
        is_boq=True,
        is_template=False,
        public=False,
        draft=False,
    )

    created = 0
    for r in rows:
        epd = r.get("epd")
        if not epd or r.get("status") == "bad_unit":
            continue  # only 'ok' rows become materials; flagged rows are resolved in the preview
        classification = None
        if r.get("category"):
            classification, _ = AssemblyCategoryTechnique.objects.get_or_create(
                category=r["category"], technique=None)
        StructuralProduct.objects.create(
            epd=epd,
            assembly=assembly,
            quantity=Decimal(str(r["quantity"])),
            input_unit=r["unit"],
            description=(r.get("description") or "")[:255],
            classification=classification,
        )
        created += 1

    BuildingAssembly.objects.create(
        building=building, assembly=assembly, quantity=1, reporting_life_cycle=50)

    return building


# ---------------------------------------------------------------------------
# Auto-fix: standard volume density (kg/m³) by material, so a kg/m³ EPD used per
# m³ (or kg) computes. Only the mass<->volume case is a defensible constant; area
# / linear / pcs mismatches need geometry the BoQ doesn't carry, so they stay flagged.
# ---------------------------------------------------------------------------
_STD_VOLUME_DENSITY = [
    (("reinforc", "rebar", "steel", "tmt", " iron"), 7850),
    (("aluminium", "aluminum"), 2700),
    (("glass",), 2500),
    (("precast", "ready mix", "ready-mix", "concrete", "rcc"), 2400),
    (("autoclaved aerated", "aerated concrete", "aac", "lightweight concrete"), 600),
    (("cement",), 1440),
    (("aggregate", "gravel", "crushed"), 1600),
    (("sand",), 1600),
    (("brick", "masonry"), 1800),
    (("timber", "wood", "plywood", "laminate", "bamboo"), 600),
    (("gypsum", "plaster", "board"), 1200),
    (("bitumen", "bituminous", "waterproof"), 1100),
]


def _std_volume_density(epd_name):
    n = (epd_name or "").lower()
    for keys, val in _STD_VOLUME_DENSITY:
        if any(k in n for k in keys):
            return val
    return None


def autofix_conversions(rows):
    """For 'bad_unit' rows in the mass<->volume case, add a standard volume density
    to the EPD (persisted) so the row becomes usable. Returns the count fixed.

    Only touches EPDs declared in kg or m³ whose BoQ unit is kg or m³ and which lack
    a volume density. Area/linear/pcs are left flagged.
    """
    fixed = 0
    for r in rows:
        if r.get("status") != "bad_unit":
            continue
        epd = r.get("epd")
        if not epd or str(epd.declared_unit) not in ("kg", "m3"):
            continue
        if str(r["unit"]) not in ("kg", "m3"):
            continue
        # already has a volume density? then it's a different problem — skip
        if any((c.get("name") == "volume density") for c in (epd.conversions or [])):
            continue
        density = _std_volume_density(epd.name)
        if not density:
            continue
        convs = list(epd.conversions or [])
        convs.append({"name": "volume density", "unit": "kg/m^3",
                      "value": str(density), "unit_description": "kilograms per cubic metre"})
        epd.conversions = convs
        epd.save(update_fields=["conversions"])
        # re-evaluate
        avail = {str(u) for u in (epd.get_available_units() or {epd.declared_unit})}
        if str(r["unit"]) in avail:
            r["status"] = "ok"
            r["reason"] = f"auto-added volume density {density} kg/m³"
            fixed += 1
    return fixed


def serialize_row(r):
    """Row -> plain dict for the preview/process JSON (EPD as id + name)."""
    epd = r.get("epd")
    return {
        "row": r["row"],
        "description": r["description"],
        "component": r["component"],
        "unit": str(r["unit"]),
        "unit_raw": r["unit_raw"],
        "quantity": r["quantity"],
        "country": r["country"],
        "epd_name": r["epd_name"],
        "epd_id": str(epd.id) if epd else None,
        "supported_units": sorted(str(u) for u in (epd.get_available_units() or {epd.declared_unit})) if epd else [],
        "status": r["status"],
        "reason": r.get("reason", ""),
    }


# ---------------------------------------------------------------------------
# Views: template download, upload+preview, process. Wired under /import-boq/.
# ---------------------------------------------------------------------------
import io
import json as _json

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, JsonResponse
from django.views.decorators.http import require_http_methods

_TEMPLATE_HEADERS = [
    "Work Description", "Category", "Unit", "Quantity",
    "BEAT Building Part", "BEAT Building Component",
    "BEAT Materials - Country", "BEAT Materials",
]


@login_required
@require_http_methods(["GET"])
def download_boq_template(request):
    """A blank BoQ template (mapped columns) + a 'Lists' tab of valid values."""
    import openpyxl
    from openpyxl.styles import Font, PatternFill

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "BoQ"
    for j, h in enumerate(_TEMPLATE_HEADERS, start=1):
        c = ws.cell(1, j, h)
        c.font = Font(bold=True)
        c.fill = PatternFill("solid", fgColor="DDEBF7")
    widths = [34, 14, 8, 10, 18, 20, 14, 40]
    for j, w in enumerate(widths, start=1):
        ws.column_dimensions[openpyxl.utils.get_column_letter(j)].width = w
    # one example row
    ws.append(["Concrete C25/30 for slab", "Structure", "m3", 158,
               "Superstructure", "Beams & Slabs", "Cambodia", "Ready-mix concrete C25/30"])

    lst = wb.create_sheet("Lists")
    lst["A1"] = "Valid BEAT Building Components"; lst["A1"].font = Font(bold=True)
    for i, name in enumerate(AssemblyCategory.objects.order_by("tag").values_list("name", flat=True), start=2):
        lst.cell(i, 1, name)
    lst["C1"] = "Valid Units"; lst["C1"].font = Font(bold=True)
    for i, u in enumerate(["m3", "m2", "m", "kg", "ton", "pcs"], start=2):
        lst.cell(i, 3, u)
    lst["E1"] = "Countries"; lst["E1"].font = Font(bold=True)
    for i, cn in enumerate(["Cambodia", "India", "Indonesia", "Thailand", "Vietnam"], start=2):
        lst.cell(i, 5, cn)

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    resp = HttpResponse(buf.read(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    resp["Content-Disposition"] = 'attachment; filename="BEAT_BoQ_template.xlsx"'
    return resp


@login_required
@require_http_methods(["POST"])
def import_boq_preview(request):
    """Parse an uploaded BoQ, resolve EPDs + units, auto-fix defensible conversions,
    and return every row's status for the preview. Read-only (creates nothing)."""
    import openpyxl
    f = request.FILES.get("file")
    if not f:
        return JsonResponse({"success": False, "error": "No file uploaded."}, status=400)
    try:
        wb = openpyxl.load_workbook(f, data_only=True, read_only=True)
    except Exception:
        return JsonResponse({"success": False, "error": "Could not read the Excel file."}, status=400)

    # first sheet that yields a valid header wins
    parsed, perr = [], None
    for ws in wb.worksheets:
        grid = [list(r) for r in ws.iter_rows(values_only=True)]
        parsed, perr = parse_boq_rows(grid)
        if parsed:
            break
    if not parsed:
        return JsonResponse({"success": False, "error": perr or "No BoQ item rows found."}, status=400)

    resolve_boq_rows(parsed)
    autofix_conversions(parsed)
    from collections import Counter
    counts = Counter(r["status"] for r in parsed)
    return JsonResponse({
        "success": True,
        "rows": [serialize_row(r) for r in parsed],
        "counts": {"ok": counts.get("ok", 0), "no_epd": counts.get("no_epd", 0),
                   "bad_unit": counts.get("bad_unit", 0), "total": len(parsed)},
    })


@login_required
@require_http_methods(["POST"])
def import_boq_process(request):
    """Create the building from the finalised materials (client-side edits applied).

    JSON: {name, country, gfa, materials: [{epd_id, unit, quantity, description, component}]}.
    Each material's unit is re-validated against the EPD server-side before creating.
    """
    from pages.models.epd import EPD
    try:
        data = _json.loads(request.body)
    except ValueError:
        return JsonResponse({"success": False, "error": "Invalid JSON."}, status=400)

    name = (data.get("name") or "").strip()
    gfa = data.get("gfa")
    if not name or not gfa:
        return JsonResponse({"success": False, "error": "Building name and GFA are required."}, status=400)
    try:
        gfa = float(gfa)
        if gfa <= 0:
            raise ValueError
    except (TypeError, ValueError):
        return JsonResponse({"success": False, "error": "GFA must be a positive number."}, status=400)

    materials = data.get("materials", [])
    if not materials:
        return JsonResponse({"success": False, "error": "No materials to import."}, status=400)

    rows, skipped = [], []
    for m in materials:
        epd = EPD.objects.filter(id=m.get("epd_id")).first()
        if not epd:
            skipped.append(m.get("epd_name") or m.get("epd_id"))
            continue
        unit = str(m.get("unit") or epd.declared_unit)
        avail = {str(u) for u in (epd.get_available_units() or {epd.declared_unit})}
        if unit not in avail:
            skipped.append(f"{epd.name} ({unit})")
            continue
        try:
            q = float(m.get("quantity"))
        except (TypeError, ValueError):
            continue
        if q <= 0:
            continue
        cat = None
        if m.get("component"):
            cat = AssemblyCategory.objects.filter(name__iexact=str(m["component"]).strip()).first()
        rows.append({"epd": epd, "unit": Unit(unit) if unit in Unit.values else unit,
                     "quantity": q, "description": m.get("description", ""),
                     "category": cat, "status": "ok"})

    if not rows:
        return JsonResponse({"success": False, "error": "No valid materials after validation.",
                             "skipped": skipped}, status=400)

    building = create_building_from_boq(
        request.user, name, data.get("country"), gfa, rows,
        building_type=None)
    return JsonResponse({"success": True, "building_uuid": str(building.uuid),
                         "created": len(rows), "skipped": skipped})
