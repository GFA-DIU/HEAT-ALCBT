import json
import uuid as uuid_lib
from decimal import Decimal, InvalidOperation

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods

from pages.models.building import Building
from pages.models.building_operation.energy_summary import EnergySummary


def _get_building(building_uuid, user):
    try:
        uuid_obj = uuid_lib.UUID(str(building_uuid))
        return Building.objects.get(uuid=uuid_obj, created_by=user)
    except (ValueError, AttributeError, Building.DoesNotExist):
        return None


def _dec(val):
    return str(val) if val is not None else None


def _serialize(summary):
    return {
        "cooling_kwh": _dec(summary.cooling_kwh),
        "is_manual_cooling": summary.is_manual_cooling,
        "ventilation_kwh": _dec(summary.ventilation_kwh),
        "is_manual_ventilation": summary.is_manual_ventilation,
        "lighting_kwh": _dec(summary.lighting_kwh),
        "is_manual_lighting": summary.is_manual_lighting,
        "lift_escalator_kwh": _dec(summary.lift_escalator_kwh),
        "is_manual_lift_escalator": summary.is_manual_lift_escalator,
        "hot_water_kwh": _dec(summary.hot_water_kwh),
        "is_manual_hot_water": summary.is_manual_hot_water,
        "plug_load_kwh": _dec(summary.plug_load_kwh),
        "is_manual_plug_load": summary.is_manual_plug_load,
        "suggested_plug_load": _dec(summary.suggested_plug_load()),
        # The percentage the user set, and the base it applies to, so the row
        # can show "20% of 768,768 kWh" instead of a bare number with no
        # visible origin.
        "plug_load_percent": _dec(summary.plug_load_percent),
        "plug_load_base": _dec(summary.plug_load_base),
        "plug_load_default_percent": _dec(summary.plug_load_default_percent),
        "plug_load_basis": summary.plug_load_basis,
        "has_plug_load": summary.has_plug_load,
        "systems_sum": _dec(summary.systems_sum),
        "total_kwh": _dec(summary.total_kwh),
        "any_components": summary.any_components,
    }


@login_required
@require_http_methods(["GET"])
def get_energy_summary(request):
    building_uuid = request.GET.get("building_uuid")
    if not building_uuid:
        return JsonResponse({"error": "building_uuid required"}, status=400)

    building = _get_building(building_uuid, request.user)
    if not building:
        return JsonResponse({"error": "Building not found"}, status=404)

    summary, created = EnergySummary.objects.get_or_create(building=building)
    if created:
        summary.recalculate()
        summary.save()

    return JsonResponse({"success": True, "summary": _serialize(summary)})


@login_required
@require_http_methods(["POST"])
def save_energy_summary(request):
    """
    Save manual energy consumption values for categories that have no system records.
    Categories with system-derived data (is_manual=False) are ignored.
    """
    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    building_uuid = data.get("building_uuid")
    if not building_uuid:
        return JsonResponse({"error": "building_uuid required"}, status=400)

    building = _get_building(building_uuid, request.user)
    if not building:
        return JsonResponse({"error": "Building not found"}, status=404)

    summary, _ = EnergySummary.objects.get_or_create(building=building)

    # Only allow writing manual values for categories without system records
    _MANUAL_FIELDS = [
        ("cooling_kwh", "is_manual_cooling"),
        ("ventilation_kwh", "is_manual_ventilation"),
        ("lighting_kwh", "is_manual_lighting"),
        ("lift_escalator_kwh", "is_manual_lift_escalator"),
        ("hot_water_kwh", "is_manual_hot_water"),
        # Plug loads have no equipment table, so they are always manually entered.
        ("plug_load_kwh", "is_manual_plug_load"),
    ]

    # --- plug load: one question, then one basis -------------------------
    #
    # has_plug_load answers whether there is any; after that exactly one of
    # plug_load_kwh and plug_load_percent may be set. Writing either clears
    # the other, which is what stops the row showing "20% of 242,249" beside
    # "0 kWh/yr" as it did before.
    if "has_plug_load" in data:
        raw = data["has_plug_load"]
        summary.has_plug_load = None if raw in (None, "", "unknown") else bool(raw)
        if summary.has_plug_load is False:
            summary.plug_load_kwh = None
            summary.plug_load_percent = None
            summary.is_manual_plug_load = False

    if "plug_load_percent" in data and summary.has_plug_load is not False:
        raw = data["plug_load_percent"]
        try:
            if raw in (None, ""):
                summary.plug_load_percent = None
            else:
                pct = Decimal(str(raw))
                if Decimal("0") <= pct <= Decimal("100"):
                    summary.plug_load_percent = pct
                    summary.plug_load_kwh = None          # one basis only
                    summary.is_manual_plug_load = False
                    if summary.has_plug_load is None:
                        summary.has_plug_load = True
        except (ValueError, TypeError, InvalidOperation):
            pass

    # A kWh figure is the other basis, so it clears the percentage.
    if data.get("plug_load_kwh") not in (None, "") and summary.has_plug_load is not False:
        summary.plug_load_percent = None
        if summary.has_plug_load is None:
            summary.has_plug_load = True

    for value_field, manual_flag in _MANUAL_FIELDS:
        if value_field in data:
            if getattr(summary, manual_flag) or getattr(summary, value_field) is None:
                raw = data[value_field]
                try:
                    setattr(summary, value_field, Decimal(str(raw)) if raw not in (None, "") else None)
                    setattr(summary, manual_flag, True)
                except (ValueError, TypeError, InvalidOperation):
                    pass

    summary.save()
    return JsonResponse({"success": True, "summary": _serialize(summary)})
