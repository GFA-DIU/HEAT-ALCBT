"""
Views for handling the multi-step building creation process.
Each step loads a template and provides necessary context data.
"""



import logging
import json

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_http_methods

from pages.forms.epds_filter_form import EPDsFilterForm
from pages.models.base import ALCBTCountryManager
from pages.models.building import BuildingCategory
from pages.models.epd import EPD, MaterialCategory

logger = logging.getLogger(__name__)
from django.db import transaction
from pages.models import Building, HotWaterSystem
from pages.forms.hot_water_system_form import HotWaterSystemForm


@login_required
@require_http_methods(["GET"])
def building_step_view(request):
    """
    Main view for handling all building creation steps.
    Returns the appropriate template based on the step parameter.
    """
    step = request.GET.get("step")
    
    if not step:
        return JsonResponse({"error": "Step parameter is required"}, status=400)
    
    # Map steps to their handlers
    step_handlers = {
        # Building Information
        "building-information/building-name-location.html": handle_name_location_step,
        "building-information/building-details.html": handle_details_step,
        
        # Operational Details
        "operational-details/operational-schedule-temperature.html": handle_schedule_temp_step,
        "operational-details/cooling-system.html": handle_cooling_system_step,
        "operational-details/ventilation-system.html": handle_ventilation_system_step,
        "operational-details/lighting-system.html": handle_lighting_system_step,
        "operational-details/lift-escalator-system.html": handle_lift_escalator_step,
        "operational-details/hot-water-system.html": handle_hot_water_step,
        
        # Operational Data Entry
        "operational-data-entry/operational-data-entry.html": handle_operational_data_step,
        
        # Building Structural Components
        "building-structural-components/building-structural-components.html": handle_structural_components_step,
    }
    
    handler = step_handlers.get(step)
    if handler:
        return handler(request)
    
    return JsonResponse({"error": f"Unknown step: {step}"}, status=404)


# Step 1.1: Building Name & Location
def handle_name_location_step(request):
    """Provide countries for the building location step."""
    context = {
        "countries": ALCBTCountryManager.get_alcbt_countries()
    }
    return render(
        request,
        "pages/add-building/components/building-information/building-name-location.html",
        context
    )


# Step 1.2: Building Details
def handle_details_step(request):
    """Provide building categories and types."""
    context = {
        "building_categories": BuildingCategory.objects.all().order_by("name")
    }
    return render(
        request,
        "pages/add-building/components/building-information/building-details.html",
        context
    )


# Step 2.1: Operational Schedule & Temperature
def handle_schedule_temp_step(request):
    """Handle operational schedule and temperature step."""
    context = {}
    return render(
        request,
        "pages/add-building/components/operational-details/operational-schedule-temperature.html",
        context
    )


# Step 2.2: Cooling System
def handle_cooling_system_step(request):
    """Handle cooling system configuration step."""
    context = {}
    return render(
        request,
        "pages/add-building/components/operational-details/cooling-system.html",
        context
    )


# Step 2.3: Ventilation System
def handle_ventilation_system_step(request):
    """Handle ventilation system configuration step."""
    context = {}
    return render(
        request,
        "pages/add-building/components/operational-details/ventilation-system.html",
        context
    )


# Step 2.4: Lighting System
def handle_lighting_system_step(request):
    """Handle lighting system configuration step."""
    context = {}
    return render(
        request,
        "pages/add-building/components/operational-details/lighting-system.html",
        context
    )


# Step 2.5: Lift & Escalator System
def handle_lift_escalator_step(request):
    """Handle lift and escalator system configuration step."""
    context = {}
    return render(
        request,
        "pages/add-building/components/operational-details/lift-escalator-system.html",
        context
    )


# Step 2.6: Hot Water System
def handle_hot_water_step(request):
    """Handle hot water system configuration step."""
    context = {}
    return render(
        request,
        "pages/add-building/components/operational-details/hot-water-system.html",
        context
    )


# Step 3: Operational Data Entry
def handle_operational_data_step(request):

    # Initialize filter form with pre-filled operational filters
    epd_filters_form = EPDsFilterForm()
    
    # Lock category and subcategory for operational products
    # Category: "Others" (ID: 9), Subcategory: "Energy carrier - delivery free user" (ID: 9.2)
    try:
        category = MaterialCategory.objects.get(category_id="9")
        subcategory = MaterialCategory.objects.get(category_id="9.2")
        
        # Set initial values and disable these fields
        epd_filters_form.fields['category'].initial = category
        epd_filters_form.fields['category'].disabled = True
        epd_filters_form.fields['subcategory'].initial = subcategory
        epd_filters_form.fields['subcategory'].disabled = True
        epd_filters_form.fields['subcategory'].queryset = MaterialCategory.objects.filter(
            level=2, parent=category
        )
        epd_filters_form.fields['childcategory'].queryset = MaterialCategory.objects.filter(
            level=3, parent=subcategory
        ).order_by("name_en")
    except MaterialCategory.DoesNotExist:
        logger.warning("Energy carrier categories not found")
    
    # Load previously saved operational products from session
    selected_products = []
    building_data = request.session.get("building_form_data", {})
    operational_data = building_data.get("operational_products", [])
    
    for product_data in operational_data:
        try:
            epd = EPD.objects.get(id=product_data["id"])
            
            # Get available units and ensure it's a list
            available_units = epd.get_available_units()
            if available_units is None:
                available_units = [epd.declared_unit]
            elif isinstance(available_units, set):
                available_units = sorted(list(available_units))
            elif not isinstance(available_units, list):
                available_units = list(available_units)
            
            selected_products.append({
                "id": str(epd.id),
                "name": epd.name,
                "country": epd.country.name if epd.country else "Unknown",
                "category": epd.category.name_en if epd.category else "Unknown",
                "description": product_data.get("description", ""),
                "selection_unit": product_data.get("unit", epd.declared_unit),
                "selection_quantity": product_data.get("quantity", ""),
                "timestamp": product_data.get("timestamp", ""),
                "op_units": available_units,
            })
        except EPD.DoesNotExist:
            logger.warning(f"EPD {product_data['id']} not found")
    
    context = {
        'epd_filters_form': epd_filters_form,
        'countries': ALCBTCountryManager.get_all_countries(),
        'selected_products': selected_products,
    }
    return render(
        request,
        "pages/add-building/components/operational-data-entry/operational-data-entry.html",
        context
    )


# Step 4: Building Structural Components
def handle_structural_components_step(request):
    """Handle building structural components step."""
    context = {}
    return render(
        request,
        "pages/add-building/components/building-structural-components/building-structural-components.html",
        context
    )


@login_required
@require_http_methods(["POST"])
def save_building_step(request):
    """
    Save data from a building creation step.
    Handles AJAX POST requests to save step data.
    """
    import json
    
    try:
        data = json.loads(request.body)
        step_key = data.get("step_key")
        step_data = data.get("data")
        logging.info(f"Saving step data for {step_key}: {step_data}", step_data)

        if not step_key or not step_data:
            return JsonResponse({"error": "Missing step_key or data"}, status=400)
        
        # Store in session for now (you can modify to save to database)
        if "building_form_data" not in request.session:
            request.session["building_form_data"] = {}
        
        request.session["building_form_data"][step_key] = step_data
        request.session.modified = True
        
        return JsonResponse({
            "success": True,
            "message": "Step data saved successfully"
        })
        
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON data"}, status=400)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


@login_required
@require_http_methods(["GET"])
def get_building_step_data(request):
    """
    Retrieve saved data for a specific building creation step.
    """
    step_key = request.GET.get("step_key")
    
    if not step_key:
        return JsonResponse({"error": "step_key parameter is required"}, status=400)
    
    building_data = request.session.get("building_form_data", {})
    step_data = building_data.get(step_key, {})
    
    return JsonResponse({
        "success": True,
        "data": step_data
    })


@login_required
@require_http_methods(["POST"])
def complete_building_setup(request):
    """
    Complete the building setup and create the building record.
    This combines all step data and creates the final building.
    """

    try:
        # Get all saved step data from session
        building_data = request.session.get("building_form_data", {})

        if not building_data:
            return JsonResponse({"error": "No building data found"}, status=400)

        # Use transaction to ensure all-or-nothing creation
        with transaction.atomic():
            # TODO: Create the actual building record here
            # For now, we need a building instance to associate HWS with
            # This assumes you have basic building data in session

            # If you already have a building created (e.g., building_id in session)
            # you can fetch it. Otherwise, you'd create it here.
            building_id = request.session.get("building_id")
            if building_id:
                try:
                    building = Building.objects.get(id=building_id, created_by=request.user)
                except Building.DoesNotExist:
                    return JsonResponse({"error": "Building not found"}, status=404)
            else:
                # If no building exists yet, return error - building should be created first
                return JsonResponse({
                    "success": False,
                    "error": "Building must be created before completing setup"
                }, status=400)

            # Process Hot Water System data
            hws_data = building_data.get("operational-details/hot-water-system", [])

            if hws_data and isinstance(hws_data, list):
                # Clear existing hot water systems for this building
                HotWaterSystem.objects.filter(building=building).delete()

                # Validate and create each hot water system
                validation_errors = {}
                for idx, system_data in enumerate(hws_data):
                    form = HotWaterSystemForm(data=system_data)

                    if form.is_valid():
                        hws = form.save(commit=False)
                        hws.building = building
                        hws.save()
                    else:
                        validation_errors[f"system_{idx}"] = form.errors

                # If there were validation errors, rollback and return errors
                if validation_errors:
                    transaction.set_rollback(True)
                    return JsonResponse({
                        "success": False,
                        "error": "Validation errors in hot water systems",
                        "errors": validation_errors
                    }, status=400)

        # Clear the session data after successful creation
        if "building_form_data" in request.session:
            del request.session["building_form_data"]

        return JsonResponse({
            "success": True,
            "message": "Building created successfully",
            "redirect_url": "/dashboard/"
        })

    except Exception as e:
        logging.error(f"Error completing building setup: {str(e)}")
        return JsonResponse({"error": str(e)}, status=500)
        return JsonResponse({"error": str(e)}, status=500)
