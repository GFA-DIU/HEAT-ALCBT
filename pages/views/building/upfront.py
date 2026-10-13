"""Upfront Carbon (A4–A5) panel: per-material breakdown + inline override editing.

GET  /building/<id>/upfront/       -> JSON breakdown (rows + totals + defaults)
POST /building/<id>/upfront/       -> save per-material overrides, returns recomputed totals
GET  /building/<id>/upfront-tab/   -> the rendered panel, loaded into the building page by htmx
"""
import json
import uuid as uuid_lib
from decimal import Decimal, InvalidOperation

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_http_methods

from pages.models.building import Building
from pages.models.assembly import StructuralProduct
from pages.views.building.impact_calculation import calculate_impacts, ImpactCalculationError
from pages.scripts.a4a5 import defaults as D
from pages.scripts.a4a5.compute import material_a4_a5


def _get_building(building_id, user):
    return Building.objects.filter(created_by=user).filter(id=building_id).first()


def _rows_and_totals(building):
    country_name = getattr(getattr(building, "country", None), "name", None) or "?"
    floor_area = float(building.total_floor_area or 0)
    rows = []
    t_a1a3 = t_a4 = t_a5w = 0.0
    for ba in building.buildingassembly_set.all():
        assembly = ba.assembly
        comp_name = assembly.name or "Untitled component"
        comp_id = str(assembly.id)
        for sp in assembly.structuralproduct_set.select_related("epd", "epd__category").all():
            try:
                impacts = calculate_impacts(
                    dimension=assembly.dimension, assembly_quantity=ba.quantity,
                    total_floor_area=floor_area, p=sp)
            except (ImpactCalculationError, ValueError, AttributeError, ZeroDivisionError):
                continue
            a1a3 = next((float(i["impact_value"]) for i in impacts
                         if i["impact_type"].impact_category == "gwp"
                         and i["impact_type"].life_cycle_stage == "a1a3"
                         and float(i["impact_value"]) > 0), 0.0)
            mass_kg = next((i.get("mass_kg") for i in impacts), None)
            cat = getattr(sp.epd, "category", None)
            cat_name = (getattr(cat, "name_en", None) or getattr(cat, "name", None)
                        or (str(cat) if cat else "")) if cat else ""
            a4, a5w, meta = material_a4_a5(
                a1a3_per_m2=Decimal(str(a1a3)), mass_kg=mass_kg, floor_area=floor_area,
                country_name=country_name, category_name=cat_name,
                scenario=sp.sourcing_scenario or None,
                waste_rate=float(sp.waste_rate) if sp.waste_rate is not None else None,
                distance_km=float(sp.a4_distance_km) if sp.a4_distance_km is not None else None,
                ef=float(sp.a4_ef) if sp.a4_ef is not None else None)
            rows.append({
                "id": sp.id,
                "component": comp_name,
                "component_id": comp_id,
                "name": (sp.epd.name or "")[:60],
                "category": cat_name,
                "mass_kg": meta.get("mass_kg"),
                "a1a3": round(a1a3, 3),
                "scenario": meta["scenario"],
                "distance_km": meta["distance_km"],
                # One entry per transport mode. There is deliberately no single
                # "ef" field: a blended factor across a sea leg and a road leg
                # is not a property of anything, and reading it as one made the
                # factor look like it fell as distance rose.
                "legs": meta["legs"],
                "legs_text": meta["legs_text"],
                "kgco2e_per_tonne": meta["kgco2e_per_tonne"],
                "waste_pct": round(meta["waste_rate"] * 100, 2),
                "a4": round(float(a4), 3),
                "a5w": round(float(a5w), 3),
                "overridden": bool(sp.sourcing_scenario or sp.waste_rate is not None
                                   or sp.a4_distance_km is not None or sp.a4_ef is not None),
            })
            t_a1a3 += a1a3; t_a4 += float(a4); t_a5w += float(a5w)
    totals = {"a1a3": round(t_a1a3, 2), "a4": round(t_a4, 2), "a5w": round(t_a5w, 2),
              "upfront": round(t_a1a3 + t_a4 + t_a5w, 2)}
    # scenario → journey defaults for this country, so the UI can prefill on change
    sdef = {}
    for k in ("local", "national", "imported"):
        legs = D.scenario_legs(k, country_name)
        sdef[k] = {
            "label": D.SCENARIOS[k]["label"],
            "legs": legs,
            "legs_text": D.describe_legs(legs),
            "distance_km": D.scenario_total_km(legs),
            "kgco2e_per_tonne": round(D.legs_tonne_km_co2(legs), 4),
        }
    return rows, totals, floor_area, country_name, sdef


@login_required
@require_http_methods(["GET", "POST"])
def building_upfront(request, building_id):
    building = _get_building(building_id, request.user)
    if not building:
        return JsonResponse({"success": False, "error": "Building not found"}, status=404)

    if request.method == "GET":
        rows, totals, floor_area, country, sdef = _rows_and_totals(building)
        return JsonResponse({
            "success": True, "rows": rows, "totals": totals,
            "floor_area": floor_area, "country": country,
            "disposal_ef": D.DISPOSAL_EF_PER_KG, "scenario_defaults": sdef,
        })

    # POST — save overrides
    try:
        data = json.loads(request.body)
    except (ValueError, TypeError):
        return JsonResponse({"success": False, "error": "Bad JSON"}, status=400)

    # only products belonging to this building's assemblies may be edited
    valid_ids = set(
        StructuralProduct.objects
        .filter(assembly__buildingassembly__building=building)
        .values_list("id", flat=True))

    def _dec(v):
        if v in (None, "", "auto"):
            return None
        try:
            return Decimal(str(v))
        except (InvalidOperation, ValueError, TypeError):
            return None

    saved = 0
    for o in data.get("overrides", []):
        try:
            sid = int(o.get("id"))
        except (TypeError, ValueError):
            continue
        if sid not in valid_ids:
            continue
        sp = StructuralProduct.objects.filter(id=sid).first()
        if not sp:
            continue
        scen = o.get("scenario") or None
        sp.sourcing_scenario = scen if scen in ("local", "national", "imported") else None
        wpct = _dec(o.get("waste_pct"))
        sp.waste_rate = (wpct / Decimal("100")) if wpct is not None else None
        sp.a4_distance_km = _dec(o.get("distance_km"))
        sp.a4_ef = _dec(o.get("ef"))
        sp.save(update_fields=["sourcing_scenario", "waste_rate", "a4_distance_km", "a4_ef"])
        saved += 1

    rows, totals, floor_area, country, sdef = _rows_and_totals(building)
    return JsonResponse({"success": True, "saved": saved, "rows": rows, "totals": totals,
                         "scenario_defaults": sdef})


@login_required
def upfront_tab(request, building_id):
    """The Upfront Carbon tab, loaded into the building page by htmx.

    Same numbers as the JSON endpoint — this renders them. Rows are grouped by
    component so the table reads the way the Assembly tab does.
    """
    building = _get_building(building_id, request.user)
    if not building:
        return render(request, "pages/building/upfront_tab.html",
                      {"not_found": True})

    rows, totals, floor_area, country_name, sdef = _rows_and_totals(building)

    groups, order = {}, []
    for r in rows:
        key = r["component_id"]
        if key not in groups:
            groups[key] = {"name": r["component"], "rows": [],
                           "a1a3": 0.0, "a4": 0.0, "a5w": 0.0}
            order.append(key)
        g = groups[key]
        g["rows"].append(r)
        g["a1a3"] += r["a1a3"]; g["a4"] += r["a4"]; g["a5w"] += r["a5w"]
    for g in groups.values():
        for k in ("a1a3", "a4", "a5w"):
            g[k] = round(g[k], 2)

    # the journeys behind every row, shown once rather than repeated per material
    journeys = [dict(key=k, **sdef[k]) for k in ("local", "national", "imported")]
    rail_share = D.national_rail_share(country_name)

    return render(request, "pages/building/upfront_tab.html", {
        "building": building,
        "country": country_name,
        "floor_area": floor_area,
        "totals": totals,
        "groups": [groups[k] for k in order],
        "journeys": journeys,
        "rail_share_pct": round(rail_share * 100),
        "ef_source": D.transport_ef(country_name)["source"],
        "disposal_ef": D.DISPOSAL_EF_PER_KG,
        "scenario_choices": D.SCENARIO_CHOICES,
        "has_rows": bool(rows),
    })
