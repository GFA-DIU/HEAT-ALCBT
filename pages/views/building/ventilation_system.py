import json
import uuid as uuid_lib
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from django.db import transaction

from pages.models.building import Building
from pages.models.building_operation import VentilationSystem
from pages.forms.ventilation_system_form import VentilationSystemForm


def get_building_by_uuid(building_uuid, user):
    """
    Helper function to get building by UUID.

    Args:
        building_uuid: str (UUID)
        user: Django user object

    Returns:
        Building object

    Raises:
        Building.DoesNotExist if building not found
        ValueError if UUID is invalid
    """
    try:
        uuid_obj = uuid_lib.UUID(str(building_uuid))
        return Building.objects.get(uuid=uuid_obj, created_by=user)
    except (ValueError, AttributeError) as e:
        raise ValueError(f"Invalid UUID format: {building_uuid}")


@login_required
@require_http_methods(["POST", "PUT"])
def create_or_update_ventilation_system(request):
    """
    Create or update a ventilation system for a building.

    POST: Create a new ventilation system
    PUT: Update an existing ventilation system

    Expected payload:
    {
        "building_uuid": str (UUID),
        "ventilation_system_id": int (optional, for updates),
        "ventilation_type": str,
        "ventilation_capacity": str,
        "baseline_efficiency": int (maps to baseline_efficiency_w_cmh),
        "operating_hours_per_day": int (optional, maps to operation_hours_per_workday),
        "operating_days_per_week": int (optional, maps to workdays_per_week),
        "operating_weeks_per_year": int (optional, maps to workweeks_per_year),
        "power_input": int (maps to total_power_input_w),
        "airflow_rate": int (maps to air_flow_rate),
        "demand_controlled_ventilation": str or bool ("yes"/"no" or true/false),
        "variable_speed_drives": str or bool ("yes"/"no" or true/false),
        "number_of_units": int (maps to number_of_units_installed),
        "annual_energy_consumption": int (optional, maps to total_energy_consumption_kwh_per_year),
        "number_of_stars": int (optional, maps to energy_efficiency_label)
    }

    Returns:
    - Success: {"success": true, "message": str, "ventilation_system": dict} (200/201)
    - Failure: {"success": false, "errors": dict} (400)
    """
    try:
        # Parse JSON payload
        data = json.loads(request.body)

        # Get building
        building_uuid = data.get('building_uuid')
        if not building_uuid:
            return JsonResponse({
                'success': False,
                'errors': {'building_uuid': ['Building UUID is required.']}
            }, status=400)

        try:
            building = get_building_by_uuid(building_uuid, request.user)
        except ValueError as e:
            return JsonResponse({
                'success': False,
                'errors': {'building_uuid': [str(e)]}
            }, status=400)
        except Building.DoesNotExist:
            return JsonResponse({
                'success': False,
                'errors': {'building_uuid': ['Building not found or you do not have permission to access it.']}
            }, status=404)

        # Check if this is an update or create
        ventilation_system_id = data.get('ventilation_system_id')
        is_update = bool(ventilation_system_id)

        if is_update:
            # Update existing ventilation system
            try:
                ventilation_system = VentilationSystem.objects.get(
                    id=ventilation_system_id,
                    building=building
                )
            except VentilationSystem.DoesNotExist:
                return JsonResponse({
                    'success': False,
                    'errors': {'ventilation_system_id': ['Ventilation system not found.']}
                }, status=404)

            form = VentilationSystemForm(data, instance=ventilation_system)
        else:
            # Create new ventilation system
            form = VentilationSystemForm(data)

        # Validate form
        if form.is_valid():
            with transaction.atomic():
                ventilation_system = form.save(commit=False)
                ventilation_system.building = building
                ventilation_system.save()

            # Prepare response data
            response_data = {
                'success': True,
                'message': 'Ventilation system updated successfully.' if is_update else 'Ventilation system created successfully.',
                'ventilation_system': {
                    'id': ventilation_system.id,
                    'ventilation_type': ventilation_system.ventilation_type,
                    'ventilation_type_display': ventilation_system.get_ventilation_type_display(),
                    'ventilation_capacity': ventilation_system.ventilation_capacity,
                    'ventilation_capacity_display': ventilation_system.get_ventilation_capacity_display(),
                    'baseline_efficiency_w_cmh': ventilation_system.baseline_efficiency_w_cmh,
                    'operation_hours_per_workday': ventilation_system.operation_hours_per_workday,
                    'workdays_per_week': ventilation_system.workdays_per_week,
                    'workweeks_per_year': ventilation_system.workweeks_per_year,
                    'total_power_input_w': ventilation_system.total_power_input_w,
                    'air_flow_rate': ventilation_system.air_flow_rate,
                    'demand_controlled_ventilation': ventilation_system.demand_controlled_ventilation,
                    'variable_speed_drives': ventilation_system.variable_speed_drives,
                    'number_of_units_installed': ventilation_system.number_of_units_installed,
                    'total_energy_consumption_kwh_per_year': ventilation_system.total_energy_consumption_kwh_per_year,
                    'energy_efficiency_label': ventilation_system.energy_efficiency_label,
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
def get_ventilation_systems(request, building_uuid):
    """
    Get all ventilation systems for a specific building.

    Args:
        building_uuid: UUID of the building

    Returns:
    - Success: {"success": true, "ventilation_systems": list} (200)
    - Failure: {"success": false, "errors": dict} (400/404)
    """
    try:
        # Get building and check permissions
        try:
            building = get_building_by_uuid(building_uuid, request.user)
        except ValueError as e:
            return JsonResponse({
                'success': False,
                'errors': {'building_uuid': [str(e)]}
            }, status=400)
        except Building.DoesNotExist:
            return JsonResponse({
                'success': False,
                'errors': {'building_uuid': ['Building not found or you do not have permission to access it.']}
            }, status=404)

        # Get all ventilation systems for this building
        ventilation_systems = VentilationSystem.objects.filter(building=building).order_by('-id')

        # Serialize data
        systems_data = []
        for system in ventilation_systems:
            systems_data.append({
                'id': system.id,
                'ventilation_type': system.ventilation_type,
                'ventilation_type_display': system.get_ventilation_type_display(),
                'ventilation_capacity': system.ventilation_capacity,
                'ventilation_capacity_display': system.get_ventilation_capacity_display(),
                'baseline_efficiency_w_cmh': system.baseline_efficiency_w_cmh,
                'operation_hours_per_workday': system.operation_hours_per_workday,
                'workdays_per_week': system.workdays_per_week,
                'workweeks_per_year': system.workweeks_per_year,
                'total_power_input_w': system.total_power_input_w,
                'air_flow_rate': system.air_flow_rate,
                'demand_controlled_ventilation': system.demand_controlled_ventilation,
                'variable_speed_drives': system.variable_speed_drives,
                'number_of_units_installed': system.number_of_units_installed,
                'total_energy_consumption_kwh_per_year': system.total_energy_consumption_kwh_per_year,
                'energy_efficiency_label': system.energy_efficiency_label,
            })

        return JsonResponse({
            'success': True,
            'ventilation_systems': systems_data
        }, status=200)

    except Exception as e:
        return JsonResponse({
            'success': False,
            'errors': {'server': [f'An unexpected error occurred: {str(e)}']}
        }, status=500)


@login_required
@require_http_methods(["DELETE"])
def delete_ventilation_system(request, system_id):
    """
    Delete a ventilation system.

    Returns:
    - Success: {"success": true, "message": str} (200)
    - Failure: {"success": false, "errors": dict} (400/404)
    """
    try:
        # Get ventilation system and check permissions
        try:
            ventilation_system = VentilationSystem.objects.get(
                id=system_id,
                building__created_by=request.user
            )
        except VentilationSystem.DoesNotExist:
            return JsonResponse({
                'success': False,
                'errors': {'system_id': ['Ventilation system not found or you do not have permission to delete it.']}
            }, status=404)

        # Delete the system
        with transaction.atomic():
            ventilation_system.delete()

        return JsonResponse({
            'success': True,
            'message': 'Ventilation system deleted successfully.'
        }, status=200)

    except Exception as e:
        return JsonResponse({
            'success': False,
            'errors': {'server': [f'An unexpected error occurred: {str(e)}']}
        }, status=500)