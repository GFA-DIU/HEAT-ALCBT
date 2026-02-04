"""
View for handling operational energy carrier selection in the add-building wizard.
This provides HTMX endpoints for filtering, selecting, and saving operational products.
"""

import logging
from datetime import datetime
import uuid as uuid_lib

from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_http_methods

from pages.forms.epds_filter_form import EPDsFilterForm
from pages.models.base import ALCBTCountryManager
from pages.models.building import Building, OperationalProduct
from pages.models.epd import EPD, MaterialCategory
from pages.views.assembly.epd_processing import get_epd_list
from pages.views.building.operational_products.operational_products import handle_op_products_save

logger = logging.getLogger(__name__)


@login_required
@require_http_methods(["GET", "POST", "PUT"])
def building_step_operational_products(request):
    """
    Handle operational products selection for the add-building wizard.
    Supports GET for listing/filtering EPDs and POST for adding/saving products.
    """
    action = request.POST.get("action") if request.method == "POST" else "list"
    
    if action == "filter":
        return handle_filter_epds(request)
    elif action == "select_op_product":
        return handle_select_product(request)
    elif action == "save_op_products":
        return handle_save_products(request)
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
    Uses the existing handle_op_products_save() function.
    """
    # Get building UUID from POST data
    building_uuid = request.POST.get("building_uuid")

    if not building_uuid:
        return JsonResponse({"error": "Building UUID is required"}, status=400)

    try:
        # Get the building instance
        uuid_obj = uuid_lib.UUID(building_uuid)
        building = Building.objects.get(uuid=uuid_obj, created_by=request.user)
    except (ValueError, Building.DoesNotExist):
        logger.error(f"Invalid building UUID or building not found: {building_uuid}")
        return JsonResponse({"error": "Invalid building UUID or building not found"}, status=400)

    # Use the existing save handler to save directly to database
    # This function deletes existing operational products and creates new ones
    handle_op_products_save(request, building.id, simulation=False)

    logger.info(f"Saved operational products to database for building {building.id}")

    # Retrieve the saved products from database to display
    saved_products = OperationalProduct.objects.filter(
        building=building
    ).select_related('epd', 'epd__country', 'epd__category')

    selected_products = []
    for op_product in saved_products:
        # Get available units and ensure it's a list
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

    context = {
        "selected_products": selected_products,
    }

    # Return just the form for HTMX swap
    response = render(
        request,
        "pages/add-building/components/operational-data-entry/_form_section.html",
        context
    )

    # Add success header for HTMX
    response['HX-Trigger'] = 'operationalProductsSaved'

    return response
