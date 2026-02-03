import json
import uuid as uuid_lib
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from django.db import transaction

from pages.models.building import Building
from pages.models.building_operation import CoolingSystemChiller, CoolingSystemAirConditioner
from pages.forms.cooling_system_form import CoolingSystemChillerForm, CoolingSystemAirConditionerForm


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
def create_or_update_cooling_system(request):
    """
    Create or update a cooling system (chiller or air conditioner) for a building.

    POST: Create a new cooling system
    PUT: Update an existing cooling system

    Expected payload:
    {
        "building_uuid": str (UUID),
        "cooling_system_id": int (optional, for updates),
        "cooling_system_type": str ("chiller" or "air_conditioner"),
        ... other fields specific to the cooling system type
    }

    Returns:
    - Success: {"success": true, "message": str, "cooling_system": dict} (200/201)
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

        # Determine cooling system type
        cooling_system_type = data.get('cooling_system_type')
        if not cooling_system_type:
            return JsonResponse({
                'success': False,
                'errors': {'cooling_system_type': ['Cooling system type is required.']}
            }, status=400)

        # Check if this is an update or create
        cooling_system_id = data.get('cooling_system_id')
        if cooling_system_id is not None:
            try:
                cooling_system_id = int(cooling_system_id)
            except (ValueError, TypeError):
                return JsonResponse({
                    'success': False,
                    'errors': {'cooling_system_id': ['Invalid cooling system ID.']}
                }, status=400)
        is_update = bool(cooling_system_id)

        if cooling_system_type == 'chiller':
            return _handle_chiller_system(request, building, data, cooling_system_id, is_update)
        elif cooling_system_type == 'air_conditioner':
            return _handle_air_conditioner_system(request, building, data, cooling_system_id, is_update)
        else:
            return JsonResponse({
                'success': False,
                'errors': {'cooling_system_type': ['Invalid cooling system type.']}
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


def _handle_chiller_system(request, building, data, cooling_system_id, is_update):
    """Handle create/update for chiller cooling systems."""
    if is_update:
        # Update existing chiller system
        try:
            chiller_system = CoolingSystemChiller.objects.get(
                id=cooling_system_id,
                building=building
            )
        except CoolingSystemChiller.DoesNotExist:
            return JsonResponse({
                'success': False,
                'errors': {'cooling_system_id': ['Chiller system not found.']}
            }, status=404)

        form = CoolingSystemChillerForm(data, instance=chiller_system)
    else:
        # Create new chiller system
        form = CoolingSystemChillerForm(data)

    # Validate form
    if form.is_valid():
        with transaction.atomic():
            chiller_system = form.save(commit=False)
            chiller_system.building = building
            chiller_system.save()

        # Prepare response data
        response_data = {
            'success': True,
            'message': 'Chiller system updated successfully.' if is_update else 'Chiller system created successfully.',
            'cooling_system': {
                'id': chiller_system.id,
                'cooling_system_type': 'chiller',
                'chiller_type': chiller_system.chiller_type,
                'chiller_type_display': chiller_system.get_chiller_type_display(),
                'year_of_installation': chiller_system.year_of_installation,
                'refrigerant_type': chiller_system.refrigerant_type,
                'refrigerant_quantity_kg': chiller_system.refrigerant_quantity_kg,
                'variable_speed_drives': chiller_system.variable_speed_drives,
                'heat_recovery_system': chiller_system.heat_recovery_system,
                'total_cooling_load_rt': chiller_system.total_cooling_load_rt,
                'baseline_leakage_factor_percent': chiller_system.baseline_leakage_factor_percent,
                'operation_hours_per_workday': chiller_system.operation_hours_per_workday,
                'workdays_per_week': chiller_system.workdays_per_week,
                'workweeks_per_year': chiller_system.workweeks_per_year,
                'baseline_cooling_efficiency_kw_h': chiller_system.baseline_cooling_efficiency_kw_h,
                'number_of_chillers': chiller_system.number_of_chillers,
                'total_chiller_system_power_input_kw': chiller_system.total_chiller_system_power_input_kw,
                'water_cooled_chiller_cooling_load_factor_percent': chiller_system.water_cooled_chiller_cooling_load_factor_percent,
                'cop': float(chiller_system.cop) if chiller_system.cop else None,
                'ip_lv': float(chiller_system.ip_lv) if chiller_system.ip_lv else None,
                'energy_efficiency_label': chiller_system.energy_efficiency_label,
                'total_energy_consumption_kwh_per_year': chiller_system.total_energy_consumption_kwh_per_year,
                'baseline_refrigerant_emission_factor': chiller_system.baseline_refrigerant_emission_factor,
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


def _handle_air_conditioner_system(request, building, data, cooling_system_id, is_update):
    """Handle create/update for air conditioner cooling systems."""
    if is_update:
        # Update existing air conditioner system
        try:
            ac_system = CoolingSystemAirConditioner.objects.get(
                id=cooling_system_id,
                building=building
            )
        except CoolingSystemAirConditioner.DoesNotExist:
            return JsonResponse({
                'success': False,
                'errors': {'cooling_system_id': ['Air conditioner system not found.']}
            }, status=404)

        form = CoolingSystemAirConditionerForm(data, instance=ac_system)
    else:
        # Create new air conditioner system
        form = CoolingSystemAirConditionerForm(data)

    # Validate form
    if form.is_valid():
        with transaction.atomic():
            ac_system = form.save(commit=False)
            ac_system.building = building
            ac_system.save()

        # Prepare response data
        response_data = {
            'success': True,
            'message': 'Air conditioner system updated successfully.' if is_update else 'Air conditioner system created successfully.',
            'cooling_system': {
                'id': ac_system.id,
                'cooling_system_type': 'air_conditioner',
                'ac_type': ac_system.ac_type,
                'ac_type_display': ac_system.get_ac_type_display(),
                'year_of_installation': ac_system.year_of_installation,
                'operation_hours_per_workday': ac_system.operation_hours_per_workday,
                'workdays_per_week': ac_system.workdays_per_week,
                'workweeks_per_year': ac_system.workweeks_per_year,
                'refrigerant_type': ac_system.refrigerant_type,
                'refrigerant_quantity_kg': ac_system.refrigerant_quantity_kg,
                'total_cooling_load_rt': ac_system.total_cooling_load_rt,
                'baseline_efficiency_kw_per_rt': float(ac_system.baseline_efficiency_kw_per_rt) if ac_system.baseline_efficiency_kw_per_rt else None,
                'baseline_refrigerant_emission_factor': ac_system.baseline_refrigerant_emission_factor,
                'baseline_leakage_factor_percent': ac_system.baseline_leakage_factor_percent,
                'total_energy_consumption_kwh_per_year': ac_system.total_energy_consumption_kwh_per_year,
                'number_of_units': ac_system.number_of_units,
                'total_system_power_kw': ac_system.total_system_power_kw,
                'cop': float(ac_system.cop) if ac_system.cop else None,
                'iseer_rating': float(ac_system.iseer_rating) if ac_system.iseer_rating else None,
                'energy_efficiency_label': ac_system.energy_efficiency_label,
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


@login_required
@require_http_methods(["GET"])
def get_cooling_systems(request, building_uuid):
    """
    Get all cooling systems (chillers and air conditioners) for a specific building.

    Args:
        building_uuid: UUID of the building

    Returns:
    - Success: {"success": true, "cooling_systems": list} (200)
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

        # Get all chiller systems for this building
        chiller_systems = CoolingSystemChiller.objects.filter(building=building).order_by('-id')

        # Get all air conditioner systems for this building
        ac_systems = CoolingSystemAirConditioner.objects.filter(building=building).order_by('-id')

        # Serialize data
        systems_data = []

        # Add chiller systems
        for system in chiller_systems:
            systems_data.append({
                'id': system.id,
                'cooling_system_type': 'chiller',
                'chiller_type': system.chiller_type,
                'chiller_type_display': system.get_chiller_type_display(),
                'year_of_installation': system.year_of_installation,
                'refrigerant_type': system.refrigerant_type,
                'refrigerant_quantity_kg': system.refrigerant_quantity_kg,
                'variable_speed_drives': system.variable_speed_drives,
                'heat_recovery_system': system.heat_recovery_system,
                'total_cooling_load_rt': system.total_cooling_load_rt,
                'baseline_leakage_factor_percent': system.baseline_leakage_factor_percent,
                'operation_hours_per_workday': system.operation_hours_per_workday,
                'workdays_per_week': system.workdays_per_week,
                'workweeks_per_year': system.workweeks_per_year,
                'baseline_cooling_efficiency_kw_h': system.baseline_cooling_efficiency_kw_h,
                'number_of_chillers': system.number_of_chillers,
                'total_chiller_system_power_input_kw': system.total_chiller_system_power_input_kw,
                'water_cooled_chiller_cooling_load_factor_percent': system.water_cooled_chiller_cooling_load_factor_percent,
                'cop': float(system.cop) if system.cop else None,
                'ip_lv': float(system.ip_lv) if system.ip_lv else None,
                'energy_efficiency_label': system.energy_efficiency_label,
                'total_energy_consumption_kwh_per_year': system.total_energy_consumption_kwh_per_year,
                'baseline_refrigerant_emission_factor': system.baseline_refrigerant_emission_factor,
            })

        # Add air conditioner systems
        for system in ac_systems:
            systems_data.append({
                'id': system.id,
                'cooling_system_type': 'air_conditioner',
                'ac_type': system.ac_type,
                'ac_type_display': system.get_ac_type_display(),
                'year_of_installation': system.year_of_installation,
                'operation_hours_per_workday': system.operation_hours_per_workday,
                'workdays_per_week': system.workdays_per_week,
                'workweeks_per_year': system.workweeks_per_year,
                'refrigerant_type': system.refrigerant_type,
                'refrigerant_quantity_kg': system.refrigerant_quantity_kg,
                'total_cooling_load_rt': system.total_cooling_load_rt,
                'baseline_efficiency_kw_per_rt': float(system.baseline_efficiency_kw_per_rt) if system.baseline_efficiency_kw_per_rt else None,
                'baseline_refrigerant_emission_factor': system.baseline_refrigerant_emission_factor,
                'baseline_leakage_factor_percent': system.baseline_leakage_factor_percent,
                'total_energy_consumption_kwh_per_year': system.total_energy_consumption_kwh_per_year,
                'number_of_units': system.number_of_units,
                'total_system_power_kw': system.total_system_power_kw,
                'cop': float(system.cop) if system.cop else None,
                'iseer_rating': float(system.iseer_rating) if system.iseer_rating else None,
                'energy_efficiency_label': system.energy_efficiency_label,
            })

        return JsonResponse({
            'success': True,
            'cooling_systems': systems_data
        }, status=200)

    except Exception as e:
        return JsonResponse({
            'success': False,
            'errors': {'server': [f'An unexpected error occurred: {str(e)}']}
        }, status=500)


@login_required
@require_http_methods(["DELETE"])
def delete_cooling_system(request, system_id):
    """
    Delete a cooling system (chiller or air conditioner).

    Requires cooling_system_type in the query parameters to know which model to delete from.

    Returns:
    - Success: {"success": true, "message": str} (200)
    - Failure: {"success": false, "errors": dict} (400/404)
    """
    try:
        # Get cooling system type from query parameters
        cooling_system_type = request.GET.get('cooling_system_type')

        if not cooling_system_type:
            return JsonResponse({
                'success': False,
                'errors': {'cooling_system_type': ['Cooling system type is required.']}
            }, status=400)

        if cooling_system_type == 'chiller':
            # Get chiller system and check permissions
            try:
                chiller_system = CoolingSystemChiller.objects.get(
                    id=system_id,
                    building__created_by=request.user
                )
            except CoolingSystemChiller.DoesNotExist:
                return JsonResponse({
                    'success': False,
                    'errors': {'system_id': ['Chiller system not found or you do not have permission to delete it.']}
                }, status=404)

            # Delete the system
            with transaction.atomic():
                chiller_system.delete()

            return JsonResponse({
                'success': True,
                'message': 'Chiller system deleted successfully.'
            }, status=200)

        elif cooling_system_type == 'air_conditioner':
            # Get air conditioner system and check permissions
            try:
                ac_system = CoolingSystemAirConditioner.objects.get(
                    id=system_id,
                    building__created_by=request.user
                )
            except CoolingSystemAirConditioner.DoesNotExist:
                return JsonResponse({
                    'success': False,
                    'errors': {'system_id': ['Air conditioner system not found or you do not have permission to delete it.']}
                }, status=404)

            # Delete the system
            with transaction.atomic():
                ac_system.delete()

            return JsonResponse({
                'success': True,
                'message': 'Air conditioner system deleted successfully.'
            }, status=200)

        else:
            return JsonResponse({
                'success': False,
                'errors': {'cooling_system_type': ['Invalid cooling system type.']}
            }, status=400)

    except Exception as e:
        return JsonResponse({
            'success': False,
            'errors': {'server': [f'An unexpected error occurred: {str(e)}']}
        }, status=500)