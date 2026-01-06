import json
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from django.db import transaction

from pages.models.building import Building
from pages.models.building_operation import LightingSystem
from pages.forms.lighting_system_form import LightingSystemForm


@login_required
@require_http_methods(["POST", "PUT"])
def create_or_update_lighting_system(request):
    """
    Create or update a lighting system for a building.

    POST: Create a new lighting system
    PUT: Update an existing lighting system

    Expected payload:
    {
        "building_id": int,
        "lighting_system_id": int (optional, for updates),
        "room_type": str,
        "area_of_room": int,
        "lighting_type": str (maps to lighting_bulb_type),
        "number_of_bulbs": int,
        "operating_hours_per_day": int (maps to operation_hours_per_workday),
        "operating_days_per_week": int (maps to workdays_per_week),
        "operating_weeks_per_year": int (maps to workweeks_per_year),
        "bulb_power_rating": int (maps to light_bulb_power_rating_w),
        "baseline_lpd": int (optional, maps to baseline_lighting_power_density),
        "installation_of_sensors": str or bool ("yes"/"no" or true/false),
        "annual_energy_consumption": int (optional, maps to total_energy_consumption_kwh_per_year),
        "number_of_stars": int (optional, maps to energy_efficiency_label)
    }

    Returns:
    - Success: {"success": true, "message": str, "lighting_system": dict} (200/201)
    - Failure: {"success": false, "errors": dict} (400)
    """
    try:
        # Parse JSON payload
        data = json.loads(request.body)

        # Get building
        building_id = data.get('building_id')
        if not building_id:
            return JsonResponse({
                'success': False,
                'errors': {'building_id': ['Building ID is required.']}
            }, status=400)

        try:
            building = Building.objects.get(id=building_id, created_by=request.user)
        except Building.DoesNotExist:
            return JsonResponse({
                'success': False,
                'errors': {'building_id': ['Building not found or you do not have permission to access it.']}
            }, status=404)

        # Check if this is an update or create
        lighting_system_id = data.get('lighting_system_id')
        is_update = bool(lighting_system_id)

        if is_update:
            # Update existing lighting system
            try:
                lighting_system = LightingSystem.objects.get(
                    id=lighting_system_id,
                    building=building
                )
            except LightingSystem.DoesNotExist:
                return JsonResponse({
                    'success': False,
                    'errors': {'lighting_system_id': ['Lighting system not found.']}
                }, status=404)

            form = LightingSystemForm(data, instance=lighting_system)
        else:
            # Create new lighting system
            form = LightingSystemForm(data)

        # Validate form
        if form.is_valid():
            with transaction.atomic():
                lighting_system = form.save(commit=False)
                lighting_system.building = building
                lighting_system.save()

            # Prepare response data
            response_data = {
                'success': True,
                'message': 'Lighting system updated successfully.' if is_update else 'Lighting system created successfully.',
                'lighting_system': {
                    'id': lighting_system.id,
                    'room_type': lighting_system.room_type,
                    'room_type_display': lighting_system.get_room_type_display(),
                    'area_of_room': lighting_system.area_of_room,
                    'lighting_bulb_type': lighting_system.lighting_bulb_type,
                    'lighting_bulb_type_display': lighting_system.get_lighting_bulb_type_display(),
                    'number_of_bulbs': lighting_system.number_of_bulbs,
                    'operation_hours_per_workday': lighting_system.operation_hours_per_workday,
                    'workdays_per_week': lighting_system.workdays_per_week,
                    'workweeks_per_year': lighting_system.workweeks_per_year,
                    'light_bulb_power_rating_w': lighting_system.light_bulb_power_rating_w,
                    'baseline_lighting_power_density': lighting_system.baseline_lighting_power_density,
                    'sensors_installed': lighting_system.sensors_installed,
                    'total_energy_consumption_kwh_per_year': lighting_system.total_energy_consumption_kwh_per_year,
                    'energy_efficiency_label': lighting_system.energy_efficiency_label,
                }
            }

            status_code = 200 if is_update else 201
            return JsonResponse(response_data, status=status_code)
        else:
            # Return validation errors
            return JsonResponse({
                'success': False,
                'errors': form.errors
            }, status=400)

    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'errors': {'json': ['Invalid JSON payload.']}
        }, status=400)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'errors': {'server': [f'An unexpected error occurred: {str(e)}']}
        }, status=500)


@login_required
@require_http_methods(["GET"])
def get_lighting_systems(request, building_id):
    """
    Get all lighting systems for a specific building.

    Returns:
    - Success: {"success": true, "lighting_systems": list} (200)
    - Failure: {"success": false, "errors": dict} (400/404)
    """
    try:
        # Get building and check permissions
        try:
            building = Building.objects.get(id=building_id, created_by=request.user)
        except Building.DoesNotExist:
            return JsonResponse({
                'success': False,
                'errors': {'building_id': ['Building not found or you do not have permission to access it.']}
            }, status=404)

        # Get all lighting systems for this building
        lighting_systems = LightingSystem.objects.filter(building=building).order_by('-id')

        # Serialize data
        systems_data = []
        for system in lighting_systems:
            systems_data.append({
                'id': system.id,
                'room_type': system.room_type,
                'room_type_display': system.get_room_type_display(),
                'area_of_room': system.area_of_room,
                'lighting_bulb_type': system.lighting_bulb_type,
                'lighting_bulb_type_display': system.get_lighting_bulb_type_display(),
                'number_of_bulbs': system.number_of_bulbs,
                'operation_hours_per_workday': system.operation_hours_per_workday,
                'workdays_per_week': system.workdays_per_week,
                'workweeks_per_year': system.workweeks_per_year,
                'light_bulb_power_rating_w': system.light_bulb_power_rating_w,
                'baseline_lighting_power_density': system.baseline_lighting_power_density,
                'sensors_installed': system.sensors_installed,
                'total_energy_consumption_kwh_per_year': system.total_energy_consumption_kwh_per_year,
                'energy_efficiency_label': system.energy_efficiency_label,
            })

        return JsonResponse({
            'success': True,
            'lighting_systems': systems_data
        }, status=200)

    except Exception as e:
        return JsonResponse({
            'success': False,
            'errors': {'server': [f'An unexpected error occurred: {str(e)}']}
        }, status=500)


@login_required
@require_http_methods(["DELETE"])
def delete_lighting_system(request, system_id):
    """
    Delete a lighting system.

    Returns:
    - Success: {"success": true, "message": str} (200)
    - Failure: {"success": false, "errors": dict} (400/404)
    """
    try:
        # Get lighting system and check permissions
        try:
            lighting_system = LightingSystem.objects.get(
                id=system_id,
                building__created_by=request.user
            )
        except LightingSystem.DoesNotExist:
            return JsonResponse({
                'success': False,
                'errors': {'system_id': ['Lighting system not found or you do not have permission to delete it.']}
            }, status=404)

        # Delete the system
        with transaction.atomic():
            lighting_system.delete()

        return JsonResponse({
            'success': True,
            'message': 'Lighting system deleted successfully.'
        }, status=200)

    except Exception as e:
        return JsonResponse({
            'success': False,
            'errors': {'server': [f'An unexpected error occurred: {str(e)}']}
        }, status=500)