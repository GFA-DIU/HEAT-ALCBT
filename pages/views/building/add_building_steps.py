"""
Views for handling the multi-step building creation process.
Each step loads a template and provides necessary context data.
"""

import logging

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_http_methods

from pages.models.base import ALCBTCountryManager
from pages.models.building import BuildingCategory


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
    """Handle operational energy carrier data entry step."""
    context = {}
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
    import json
    
    try:
        # Get all saved step data from session
        building_data = request.session.get("building_form_data", {})
        
        if not building_data:
            return JsonResponse({"error": "No building data found"}, status=400)
        
        # TODO: Create the actual building record here
        # You'll need to process the form data and create Building, 
        # BuildingOperationalInfo, and related objects
        
        # For now, just clear the session data
        if "building_form_data" in request.session:
            del request.session["building_form_data"]
        
        return JsonResponse({
            "success": True,
            "message": "Building created successfully",
            "redirect_url": "/dashboard/"
        })
        
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)
        return JsonResponse({"error": str(e)}, status=500)
        return JsonResponse({"error": str(e)}, status=500)
