"""
View for handling operational schedule and temperature data in the add-building wizard.
"""

import json
import logging
import uuid as uuid_lib

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_http_methods

from pages.models.building import Building

logger = logging.getLogger(__name__)


@login_required
@require_http_methods(["GET", "POST"])
def building_step_operational_schedule(request):
    """
    Handle operational schedule and temperature data for the add-building wizard.

    GET: Returns form with existing data (if any)
    POST: Saves operational schedule and temperature data
    """

    if request.method == "GET":
        return handle_get_schedule(request)
    else:
        return handle_save_schedule(request)


def handle_get_schedule(request):
    """
    Get existing operational schedule data for a building.
    Returns JSON with the data to populate the form.
    """
    building_uuid = request.GET.get("building_uuid")

    if not building_uuid:
        return JsonResponse({"error": "Building UUID is required"}, status=400)

    try:
        uuid_obj = uuid_lib.UUID(building_uuid)
        building = Building.objects.get(uuid=uuid_obj, created_by=request.user)
    except (ValueError, Building.DoesNotExist):
        return JsonResponse({"error": "Building not found"}, status=404)

    # Return existing data
    data = {
        "success": True,
        "data": {
            "number_of_residents": building.num_residents,
            "annual_operating_hours_per_day": building.hours_per_workday,
            "annual_operating_days_per_week": building.workdays_per_week,
            "annual_operating_weeks_per_year": building.weeks_per_year,
            "room_heating_temperature": float(building.heating_temp) if building.heating_temp else None,
            "heating_temperature_unit": building.heating_temp_unit,
            "room_cooling_temperature": float(building.cooling_temp) if building.cooling_temp else None,
            "cooling_temperature_unit": building.cooling_temp_unit,
        }
    }

    return JsonResponse(data)


def handle_save_schedule(request):
    """
    Save operational schedule and temperature data to the building.

    Expected POST data (JSON):
    {
        "building_uuid": str,
        "number_of_residents": int,
        "annual_operating_hours_per_day": int,
        "annual_operating_days_per_week": int,
        "annual_operating_weeks_per_year": int,
        "room_heating_temperature": float,
        "heating_temperature_unit": str ("celsius" or "fahrenheit"),
        "room_cooling_temperature": float,
        "cooling_temperature_unit": str ("celsius" or "fahrenheit")
    }
    """
    try:
        data = json.loads(request.body)
        building_uuid = data.get("building_uuid")

        if not building_uuid:
            return JsonResponse({"success": False, "error": "Building UUID is required"}, status=400)

        # Get building
        try:
            uuid_obj = uuid_lib.UUID(building_uuid)
            building = Building.objects.get(uuid=uuid_obj, created_by=request.user)
        except (ValueError, Building.DoesNotExist):
            return JsonResponse({"success": False, "error": "Building not found"}, status=404)

        # Update operational schedule fields
        building.num_residents = data.get("number_of_residents")
        building.hours_per_workday = data.get("annual_operating_hours_per_day")
        building.workdays_per_week = data.get("annual_operating_days_per_week")
        building.weeks_per_year = data.get("annual_operating_weeks_per_year")

        # Update temperature fields
        building.heating_temp = data.get("room_heating_temperature")
        building.heating_temp_unit = data.get("heating_temperature_unit")
        building.cooling_temp = data.get("room_cooling_temperature")
        building.cooling_temp_unit = data.get("cooling_temperature_unit")

        building.save()

        logger.info(f"Saved operational schedule for building {building.id}")

        return JsonResponse({
            "success": True,
            "message": "Operational schedule and temperature saved successfully"
        })

    except json.JSONDecodeError:
        return JsonResponse({"success": False, "error": "Invalid JSON data"}, status=400)
    except Exception as e:
        logger.exception(f"Error saving operational schedule: {str(e)}")
        return JsonResponse({"success": False, "error": str(e)}, status=500)
