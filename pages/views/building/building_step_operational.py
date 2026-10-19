"""
View for handling operational energy carrier selection in the add-building wizard.
This provides HTMX endpoints for filtering, selecting, and saving operational products.
"""

import logging
import json
from datetime import datetime
from decimal import Decimal, InvalidOperation
import uuid as uuid_lib

from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_http_methods
from django.db.models import Sum

from pages.forms.epds_filter_form import EPDsFilterForm
from pages.models.base import ALCBTCountryManager
from pages.models.building import Building, ConstructionProduct, OperationalProduct
from pages.models.building_operation.energy_summary import EnergySummary
from pages.models.epd import EPD, MaterialCategory, Unit
from pages.scripts.a4a5.construction import construction_energy
from pages.views.assembly.epd_processing import get_epd_list
from pages.views.building.operational_products.operational_products import handle_op_products_save

logger = logging.getLogger(__name__)


def _to_kwh(prod):
    """Convert an OperationalProduct's quantity to kWh using EPD conversion factors.

    Returns None if conversion is not possible (missing data or unsupported unit pair).
    Only meaningful when the EPD's declared_unit is kWh (i.e. it represents an energy carrier).
    """
    try:
        qty = Decimal(str(prod.quantity))
        declared = prod.epd.declared_unit
        input_unit = (prod.input_unit or '').lower().strip()

        def get_conv(key):
            convs = prod.epd.conversions or []
            v = next((c['value'] for c in convs if c['unit'] == key), None)
            return Decimal(str(v)) if v is not None else None

        if declared == Unit.KWH:
            if input_unit == Unit.KWH:
                return qty
            if input_unit == Unit.M3:
                kwh_per_kg = get_conv('kg') or get_conv('-')
                kg_per_m3 = get_conv('kg/m^3')
                if kwh_per_kg and kg_per_m3:
                    return qty * kwh_per_kg * kg_per_m3
            if input_unit == Unit.LITER:
                kwh_per_kg = get_conv('kg') or get_conv('-')
                kg_per_m3 = get_conv('kg/m^3')
                if kwh_per_kg and kg_per_m3:
                    return qty * kwh_per_kg * kg_per_m3 / Decimal('1000')
            if input_unit == Unit.KG:
                kwh_per_kg = get_conv('kg') or get_conv('-')
                if kwh_per_kg:
                    return qty * kwh_per_kg
    except Exception:
        pass
    return None


@login_required
@require_http_methods(["GET", "POST", "PUT", "DELETE"])
def building_step_operational_products(request):
    """
    Handle operational products selection for the add-building wizard.
    Supports GET for listing/filtering EPDs and POST for adding/saving products.
    """

    action = "list"

    if request.method == "POST":
        # Try to get action from JSON body first
        if request.content_type == 'application/json':
            try:
                data = json.loads(request.body)
                action = data.get("action", "list")
            except json.JSONDecodeError:
                action = request.POST.get("action", "list")
        else:
            # Fall back to form data
            action = request.POST.get("action", "list")

    if action == "filter":
        return handle_filter_epds(request)
    elif action == "select_op_product":
        return handle_select_product(request)
    elif action == "save_op_products":
        return handle_save_products(request)
    elif action == "save_constr_products":
        return handle_save_construction_products(request)
    elif action == "delete_op_product":
        return handle_delete_product(request)
    else:
        # Default: return EPD list
        return handle_filter_epds(request)


def handle_filter_epds(request):
    """Filter and return operational EPD list."""
    # Get EPD list filtered for operational products
    # get_epd_list returns (page, dimension) tuple
    epd_list, dimension = get_epd_list(request, dimension=None, operational=True)
    
    # Prepare filter form
    form = EPDsFilterForm(request.POST if request.method == "POST" else request.GET)
    
    # Lock category and subcategory for operational products
    try:
        category = MaterialCategory.objects.get(category_id="9")
        subcategory = MaterialCategory.objects.get(category_id="9.2")
        
        form.fields['category'].initial = category
        form.fields['category'].disabled = True
        form.fields['subcategory'].initial = subcategory
        form.fields['subcategory'].disabled = True
        form.fields['subcategory'].queryset = MaterialCategory.objects.filter(
            level=2, parent=category
        )
        form.fields['childcategory'].queryset = MaterialCategory.objects.filter(
            level=3, parent=subcategory
        ).order_by("name_en")
    except MaterialCategory.DoesNotExist:
        logger.warning("Energy carrier categories not found")
    
    # Build filter string for pagination from request parameters
    req = request.POST if request.method == "POST" else request.GET
    filter_params = []
    for key in ['search_query', 'country', 'childcategory', 'type']:
        value = req.get(key)
        if value:
            filter_params.append(f"{key}={value}")
    filters_str = "&".join(filter_params)
    
    context = {
        "epd_list": epd_list,
        "filters": filters_str,
        "epd_filters_form": form,
    }
    
    return render(
        request,
        "pages/add-building/components/operational-data-entry/_epd_list.html",
        context
    )


def handle_select_product(request):
    """Add an EPD to the selected products list."""
    epd_id = request.POST.get("epd_id")
    
    if not epd_id:
        return HttpResponse("EPD ID required", status=400)
    
    try:
        epd = EPD.objects.get(id=epd_id)
        
        # Get available units and ensure it's a list
        available_units = epd.get_available_units()
        if available_units is None:
            available_units = [epd.declared_unit]
        elif isinstance(available_units, set):
            available_units = sorted(list(available_units))
        elif not isinstance(available_units, list):
            available_units = list(available_units)
        
        # Prepare EPD data for display
        epd_data = {
            "id": str(epd.id),
            "name": epd.name,
            "country": epd.country.name if epd.country else "Unknown",
            "category": epd.category.name_en if epd.category else "Unknown",
            "description": "",
            "selection_unit": epd.declared_unit,
            "selection_quantity": "",
            "timestamp": datetime.now().strftime("%Y%m%d%H%M%S%f"),
            "op_units": available_units,
        }
        
        context = {"epd": epd_data}

        # A5.2 site energy uses the same carriers but a different row template,
        # so the two phases cannot collide in the POST data.
        if request.POST.get("phase") == "construction":
            return render(
                request,
                "pages/add-building/components/operational-data-entry/"
                "_selected_construction_product.html",
                context,
            )

        return render(
            request,
            "pages/add-building/components/operational-data-entry/_selected_product.html",
            context
        )
        
    except EPD.DoesNotExist:
        return HttpResponse("EPD not found", status=404)


def handle_save_products(request):
    """
    Save selected operational products directly to database.
    Validates total kWh of all carriers against EnergySummary before saving.
    """
    building_uuid = request.POST.get("building_uuid")
    if not building_uuid:
        return JsonResponse({"error": "Building UUID is required"}, status=400)

    try:
        uuid_obj = uuid_lib.UUID(building_uuid)
        building = Building.objects.get(uuid=uuid_obj, created_by=request.user)
    except (ValueError, Building.DoesNotExist):
        logger.error(f"Invalid building UUID or building not found: {building_uuid}")
        return JsonResponse({"error": "Invalid building UUID or building not found"}, status=400)

    # Pre-save validation. We only HARD-BLOCK when the user has stated an actual
    # metered bill total (total_override_kwh): the carriers are the fuels that make
    # up that bill, so their sum shouldn't exceed it (beyond a rounding tolerance).
    # When the only reference is the SYSTEMS estimate, we do NOT block — that
    # estimate omits plug/other loads, so a real bill legitimately exceeds it (the
    # dashboard shows a soft energy-mismatch warning instead).
    try:
        energy_summary = EnergySummary.objects.filter(building=building).first()
        bill_total = energy_summary.total_override_kwh if energy_summary else None
        if bill_total is not None:
            total_limit = Decimal(str(bill_total))

            # Parse submitted carriers from POST data (mirrors handle_op_products_save logic)
            submitted = {}
            for key, value in request.POST.items():
                if key.startswith("material_") and "_quantity" in key:
                    parts = key.split("_")
                    epd_id = parts[1]
                    timestamp = parts[-1]
                    submitted[epd_id + timestamp] = {
                        "epd_id": epd_id,
                        "quantity": value,
                        "unit": request.POST.get(f"material_{epd_id}_unit_{timestamp}", ""),
                    }

            epd_ids = [v["epd_id"] for v in submitted.values()]
            epds_by_id = {str(e.id): e for e in EPD.objects.filter(id__in=epd_ids)}

            total_kwh = Decimal("0")
            for item in submitted.values():
                epd = epds_by_id.get(item["epd_id"])
                if not epd:
                    continue
                try:
                    qty = Decimal(str(item["quantity"]))
                except (InvalidOperation, ValueError):
                    continue

                class _FakeProd:
                    pass

                prod = _FakeProd()
                prod.epd = epd
                prod.quantity = qty
                prod.input_unit = item["unit"]

                kwh = _to_kwh(prod)
                if kwh is not None:
                    total_kwh += kwh

            tolerance = total_limit * Decimal("0.02")
            if total_kwh > total_limit + tolerance:
                response = JsonResponse({
                    "error": (
                        f"The total energy of all carriers ({round(total_kwh, 1)} kWh) "
                        f"exceeds your stated total annual energy from bills ({total_limit} kWh). "
                        f"Please check your carrier quantities or update the bill total."
                    )
                }, status=400)
                response['HX-Reswap'] = 'none'
                return response
    except Exception as e:
        logger.error(f"Energy carrier validation error: {e}")

    handle_op_products_save(request, building.id, simulation=False)
    logger.info(f"Saved operational products to database for building {building.id}")

    saved_products = OperationalProduct.objects.filter(
        building=building
    ).select_related('epd', 'epd__country', 'epd__category')

    selected_products = []
    for op_product in saved_products:
        available_units = op_product.epd.get_available_units()
        if available_units is None:
            available_units = [op_product.epd.declared_unit]
        elif isinstance(available_units, set):
            available_units = sorted(list(available_units))
        elif not isinstance(available_units, list):
            available_units = list(available_units)

        selected_products.append({
            "id": str(op_product.epd.id),
            "name": op_product.epd.name,
            "country": op_product.epd.country.name if op_product.epd.country else "Unknown",
            "category": op_product.epd.category.name_en if op_product.epd.category else "Unknown",
            "description": op_product.description,
            "selection_unit": op_product.input_unit,
            "selection_quantity": op_product.quantity,
            "timestamp": datetime.now().strftime("%Y%m%d%H%M%S%f"),
            "op_units": available_units,
        })

    context = {"selected_products": selected_products}

    response = render(
        request,
        "pages/add-building/components/operational-data-entry/_form_section.html",
        context
    )
    response['HX-Trigger'] = 'operationalProductsSaved'
    return response


def handle_delete_product(request):
    """
    Delete a specific operational product from the building.
    """

    try:
        data = json.loads(request.body)
        building_uuid = data.get("building_uuid")
        epd_id = data.get("epd_id")

        if not building_uuid or not epd_id:
            return JsonResponse({"success": False, "error": "Missing required fields"}, status=400)

        # Get the building instance
        try:
            uuid_obj = uuid_lib.UUID(building_uuid)
            building = Building.objects.get(uuid=uuid_obj, created_by=request.user)
        except (ValueError, Building.DoesNotExist):
            return JsonResponse({"success": False, "error": "Building not found"}, status=404)

        # Delete the operational product
        deleted_count, _ = OperationalProduct.objects.filter(
            building=building,
            epd_id=epd_id
        ).delete()

        if deleted_count > 0:
            logger.info(f"Deleted operational product {epd_id} from building {building.id}")
            return JsonResponse({
                "success": True,
                "message": "Energy carrier removed successfully"
            })
        else:
            return JsonResponse({
                "success": False,
                "error": "Energy carrier not found"
            }, status=404)

    except json.JSONDecodeError:
        return JsonResponse({"success": False, "error": "Invalid JSON data"}, status=400)
    except Exception as e:
        logger.exception(f"Error deleting operational product: {str(e)}")
        return JsonResponse({"success": False, "error": str(e)}, status=500)


@login_required
@require_http_methods(["GET"])
def get_building_total_kwh(request, building_uuid):
    """
    Return the sum of all operational product quantities with unit 'kwh' for a building.
    Used to compute the lift & escalator annual energy consumption default (total × 7.5%).
    """
    try:
        uuid_obj = uuid_lib.UUID(str(building_uuid))
        building = Building.objects.get(uuid=uuid_obj, created_by=request.user)
    except (ValueError, Building.DoesNotExist):
        return JsonResponse({"success": False, "error": "Building not found"}, status=404)


    total = OperationalProduct.objects.filter(
        building=building,
        input_unit='kwh'
    ).aggregate(total=Sum('quantity'))['total'] or 0

    # The lift estimate is computed here, by the same function the summary
    # uses, rather than left to the caller to multiply.
    #
    # The lift form used to take total_kwh and apply 7.5% itself. total_kwh is
    # every operational product in kWh - the whole electricity entry, plug and
    # equipment loads included - while the summary applies 7.5% to cooling,
    # ventilation, lighting and hot water only. The same building showed
    # 69,189.15 on the form and 57,657.6 in the summary.
    from pages.models.building_operation.energy_summary import (
        EnergySummary, lift_estimate_kwh,
    )
    summary = EnergySummary.objects.filter(building=building).first()
    estimate = 0.0
    if summary:
        estimate = float(lift_estimate_kwh(
            summary.cooling_kwh, summary.ventilation_kwh,
            summary.lighting_kwh, summary.hot_water_kwh,
        ))

    return JsonResponse({
        "success": True,
        "total_kwh": float(total),
        "lift_estimate_kwh": estimate,
    })


def handle_save_construction_products(request):
    """Save construction-phase energy carriers (RICS A5.2).

    Deliberately separate from handle_save_products. Operational carriers are
    validated against the building's metered annual bill; site energy has no
    such reference - it is whatever the site used - so applying that check
    would reject legitimate data. Keeping the handlers apart also means no
    query over operational products can pick up site diesel.
    """
    building_uuid = request.POST.get("building_uuid")
    if not building_uuid:
        return JsonResponse({"error": "Building UUID is required"}, status=400)

    try:
        uuid_obj = uuid_lib.UUID(building_uuid)
        building = Building.objects.get(uuid=uuid_obj, created_by=request.user)
    except (ValueError, Building.DoesNotExist):
        return JsonResponse(
            {"error": "Invalid building UUID or building not found"}, status=400)

    submitted = {}
    for key, value in request.POST.items():
        if key.startswith("constr_") and "_quantity_" in key:
            parts = key.split("_")
            epd_id, timestamp = parts[1], parts[-1]
            submitted[epd_id + timestamp] = {
                "epd_id": epd_id,
                "quantity": value,
                "unit": request.POST.get("constr_%s_unit_%s" % (epd_id, timestamp), ""),
                "description": request.POST.get(
                    "constr_%s_description_%s" % (epd_id, timestamp), ""),
            }

    epds = {str(e.id): e for e in
            EPD.objects.filter(id__in=[v["epd_id"] for v in submitted.values()])}

    ConstructionProduct.objects.filter(building=building).delete()
    saved = 0
    for item in submitted.values():
        epd = epds.get(item["epd_id"])
        if not epd or not item["unit"]:
            continue
        try:
            qty = Decimal(str(item["quantity"]))
        except (InvalidOperation, ValueError, TypeError):
            continue
        if qty <= 0:
            continue
        ConstructionProduct.objects.create(
            building=building, epd=epd, quantity=qty,
            input_unit=item["unit"], description=item["description"] or "")
        saved += 1

    logger.info("Saved %d construction energy carriers for building %s",
                saved, building.id)

    a5_2, rows, notes = construction_energy(
        ConstructionProduct.objects.filter(building=building).select_related("epd"),
        building.total_floor_area)
    return JsonResponse({
        "success": True, "saved": saved,
        "a5_2_per_m2": float(round(a5_2, 3)),
        "rows": rows, "notes": notes,
    })
