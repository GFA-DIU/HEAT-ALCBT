import json
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.db import transaction

from pages.models.building import Building
from pages.models.building_operation import HotWaterSystem
from pages.forms.hot_water_system_form import HotWaterSystemForm


@login_required
@require_http_methods(["POST", "PUT"])
def create_or_update_hot_water_system(request):
    """
    Create or update a hot water system for a building.

    POST: Create a new hot water system
    PUT: Update an existing hot water system

    Expected payload:
    {
        "building_id": int,
        "hot_water_system_id": int (optional, for updates),
        "type_of_hot_water_system": str,
        "fuel_type": str,
        "operating_hours_per_day": float,
        "operating_days_per_week": int,
        "operating_weeks_per_year": int,
        "fuel_consumption": float,
        "power_input": float,
        "baseline_efficiency": float,
        "equipment_efficiency_level": float,
        "heat_recovery_system": str or bool ("yes"/"no" or true/false),
        "number_of_equipment": int,
        "energy_efficiency_label": str (optional),
        "number_of_stars": int (optional)
    }

    Returns:
    - Success: {"success": true, "message": str, "hot_water_system": dict} (200/201)
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
        hot_water_system_id = data.get('hot_water_system_id')
        is_update = bool(hot_water_system_id)

        if is_update:
            # Update existing hot water system
            try:
                hot_water_system = HotWaterSystem.objects.get(
                    id=hot_water_system_id,
                    building=building
                )
            except HotWaterSystem.DoesNotExist:
                return JsonResponse({
                    'success': False,
                    'errors': {'hot_water_system_id': ['Hot water system not found.']}
                }, status=404)

            form = HotWaterSystemForm(data, instance=hot_water_system)
        else:
            # Create new hot water system
            form = HotWaterSystemForm(data)

        # Validate form
        if form.is_valid():
            with transaction.atomic():
                hot_water_system = form.save(commit=False)
                hot_water_system.building = building
                hot_water_system.save()

            # Prepare response data
            response_data = {
                'success': True,
                'message': 'Hot water system updated successfully.' if is_update else 'Hot water system created successfully.',
                'hot_water_system': {
                    'id': hot_water_system.id,
                    'type_of_hot_water_system': hot_water_system.type_of_hot_water_system,
                    'type_of_hot_water_system_display': hot_water_system.get_type_of_hot_water_system_display(),
                    'fuel_type': hot_water_system.fuel_type,
                    'fuel_type_display': hot_water_system.get_fuel_type_display(),
                    'operating_hours_per_day': str(hot_water_system.operating_hours_per_day),
                    'operating_days_per_week': hot_water_system.operating_days_per_week,
                    'operating_weeks_per_year': hot_water_system.operating_weeks_per_year,
                    'fuel_consumption': str(hot_water_system.fuel_consumption),
                    'power_input': str(hot_water_system.power_input),
                    'baseline_efficiency': str(hot_water_system.baseline_efficiency),
                    'equipment_efficiency_level': str(hot_water_system.equipment_efficiency_level),
                    'heat_recovery_system': hot_water_system.heat_recovery_system,
                    'number_of_equipment': hot_water_system.number_of_equipment,
                    'energy_efficiency_label': hot_water_system.energy_efficiency_label,
                    'energy_efficiency_label_display': hot_water_system.get_energy_efficiency_label_display() if hot_water_system.energy_efficiency_label else None,
                    'number_of_stars': hot_water_system.number_of_stars,
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
def get_hot_water_systems(request, building_id):
    """
    Get all hot water systems for a specific building.

    Returns:
    - Success: {"success": true, "hot_water_systems": list} (200)
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

        # Get all hot water systems for this building
        hot_water_systems = HotWaterSystem.objects.filter(building=building).order_by('-id')

        # Serialize data
        systems_data = []
        for system in hot_water_systems:
            systems_data.append({
                'id': system.id,
                'type_of_hot_water_system': system.type_of_hot_water_system,
                'type_of_hot_water_system_display': system.get_type_of_hot_water_system_display(),
                'fuel_type': system.fuel_type,
                'fuel_type_display': system.get_fuel_type_display(),
                'operating_hours_per_day': str(system.operating_hours_per_day),
                'operating_days_per_week': system.operating_days_per_week,
                'operating_weeks_per_year': system.operating_weeks_per_year,
                'fuel_consumption': str(system.fuel_consumption),
                'power_input': str(system.power_input),
                'baseline_efficiency': str(system.baseline_efficiency),
                'equipment_efficiency_level': str(system.equipment_efficiency_level),
                'heat_recovery_system': system.heat_recovery_system,
                'number_of_equipment': system.number_of_equipment,
                'energy_efficiency_label': system.energy_efficiency_label,
                'energy_efficiency_label_display': system.get_energy_efficiency_label_display() if system.energy_efficiency_label else None,
                'number_of_stars': system.number_of_stars,
            })

        return JsonResponse({
            'success': True,
            'hot_water_systems': systems_data
        }, status=200)

    except Exception as e:
        return JsonResponse({
            'success': False,
            'errors': {'server': [f'An unexpected error occurred: {str(e)}']}
        }, status=500)


@login_required
@require_http_methods(["DELETE"])
def delete_hot_water_system(request, system_id):
    """
    Delete a hot water system.

    Returns:
    - Success: {"success": true, "message": str} (200)
    - Failure: {"success": false, "errors": dict} (400/404)
    """
    try:
        # Get hot water system and check permissions
        try:
            hot_water_system = HotWaterSystem.objects.get(
                id=system_id,
                building__created_by=request.user
            )
        except HotWaterSystem.DoesNotExist:
            return JsonResponse({
                'success': False,
                'errors': {'system_id': ['Hot water system not found or you do not have permission to delete it.']}
            }, status=404)

        # Delete the system
        with transaction.atomic():
            hot_water_system.delete()

        return JsonResponse({
            'success': True,
            'message': 'Hot water system deleted successfully.'
        }, status=200)

    except Exception as e:
        return JsonResponse({
            'success': False,
            'errors': {'server': [f'An unexpected error occurred: {str(e)}']}
        }, status=500)


@login_required
@require_http_methods(["POST"])
def save_multiple_hot_water_systems(request):
    """
    Save multiple hot water systems for a building at once.
    This replaces all existing hot water systems for the building.

    Expected payload:
    {
        "building_id": int,
        "hot_water_systems": [
            {
                "type_of_hot_water_system": str,
                "fuel_type": str,
                ... (all other fields)
            },
            ...
        ]
    }

    Returns:
    - Success: {"success": true, "message": str, "hot_water_systems": list} (200)
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

        # Get hot water systems data
        systems_data = data.get('hot_water_systems', [])

        if not isinstance(systems_data, list):
            return JsonResponse({
                'success': False,
                'errors': {'hot_water_systems': ['hot_water_systems must be a list.']}
            }, status=400)

        # Validate all systems before saving
        validated_systems = []
        all_errors = {}

        for index, system_data in enumerate(systems_data):
            form = HotWaterSystemForm(system_data)
            if form.is_valid():
                validated_systems.append(form)
            else:
                all_errors[f'system_{index}'] = form.errors

        # If there are any validation errors, return them
        if all_errors:
            return JsonResponse({
                'success': False,
                'errors': all_errors
            }, status=400)

        # Save all systems in a transaction
        with transaction.atomic():
            # Delete existing hot water systems for this building
            HotWaterSystem.objects.filter(building=building).delete()

            # Create new systems
            created_systems = []
            for form in validated_systems:
                system = form.save(commit=False)
                system.building = building
                system.save()
                created_systems.append(system)

        # Prepare response
        systems_response = []
        for system in created_systems:
            systems_response.append({
                'id': system.id,
                'type_of_hot_water_system': system.type_of_hot_water_system,
                'type_of_hot_water_system_display': system.get_type_of_hot_water_system_display(),
                'fuel_type': system.fuel_type,
                'fuel_type_display': system.get_fuel_type_display(),
                'operating_hours_per_day': str(system.operating_hours_per_day),
                'operating_days_per_week': system.operating_days_per_week,
                'operating_weeks_per_year': system.operating_weeks_per_year,
                'fuel_consumption': str(system.fuel_consumption),
                'power_input': str(system.power_input),
                'baseline_efficiency': str(system.baseline_efficiency),
                'equipment_efficiency_level': str(system.equipment_efficiency_level),
                'heat_recovery_system': system.heat_recovery_system,
                'number_of_equipment': system.number_of_equipment,
                'energy_efficiency_label': system.energy_efficiency_label,
                'energy_efficiency_label_display': system.get_energy_efficiency_label_display() if system.energy_efficiency_label else None,
                'number_of_stars': system.number_of_stars,
            })

        return JsonResponse({
            'success': True,
            'message': f'{len(created_systems)} hot water system(s) saved successfully.',
            'hot_water_systems': systems_response
        }, status=200)

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