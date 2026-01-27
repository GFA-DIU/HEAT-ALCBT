import json
import uuid as uuid_lib
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from django.db import transaction

from pages.models.building import Building
from pages.models.building_operation import LiftEscalatorSystem
from pages.forms.lift_escalator_system_form import LiftEscalatorSystemForm


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
def create_or_update_lift_escalator_system(request):
    """
    Create or update a lift & escalator system for a building.

    POST: Create a new lift & escalator system
    PUT: Update an existing lift & escalator system

    Expected payload:
    {
        "building_uuid": str (UUID),
        "lift_escalator_system_id": int (optional, for updates),
        "number_of_lifts": int,
        "lift_regenerative_features": str or bool ("yes"/"no" or true/false),
        "vvvf_sleep_mode": str or bool ("yes"/"no" or true/false),
        "annual_energy_consumption": int (optional)
    }

    Returns:
    - Success: {"success": true, "message": str, "lift_escalator_system": dict} (200/201)
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
        lift_escalator_system_id = data.get('lift_escalator_system_id')
        is_update = bool(lift_escalator_system_id)

        if is_update:
            # Update existing lift & escalator system
            try:
                lift_escalator_system = LiftEscalatorSystem.objects.get(
                    id=lift_escalator_system_id,
                    building=building
                )
            except LiftEscalatorSystem.DoesNotExist:
                return JsonResponse({
                    'success': False,
                    'errors': {'lift_escalator_system_id': ['Lift & escalator system not found.']}
                }, status=404)

            form = LiftEscalatorSystemForm(data, instance=lift_escalator_system)
        else:
            # Create new lift & escalator system
            form = LiftEscalatorSystemForm(data)

        # Validate form
        if form.is_valid():
            with transaction.atomic():
                lift_escalator_system = form.save(commit=False)
                lift_escalator_system.building = building
                lift_escalator_system.save()

            # Prepare response data
            response_data = {
                'success': True,
                'message': 'Lift & escalator system updated successfully.' if is_update else 'Lift & escalator system created successfully.',
                'lift_escalator_system': {
                    'id': lift_escalator_system.id,
                    'number_of_lifts': lift_escalator_system.number_of_lifts,
                    'lift_regenerative_features': lift_escalator_system.lift_regenerative_features,
                    'vvvf_sleep_mode': lift_escalator_system.vvvf_sleep_mode,
                    'annual_energy_consumption_kwh': lift_escalator_system.annual_energy_consumption_kwh,
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
def get_lift_escalator_systems(request, building_uuid):
    """
    Get all lift & escalator systems for a specific building.

    Args:
        building_uuid: UUID of the building

    Returns:
    - Success: {"success": true, "lift_escalator_systems": list} (200)
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

        # Get all lift & escalator systems for this building
        lift_escalator_systems = LiftEscalatorSystem.objects.filter(building=building).order_by('-id')

        # Serialize data
        systems_data = []
        for system in lift_escalator_systems:
            systems_data.append({
                'id': system.id,
                'number_of_lifts': system.number_of_lifts,
                'lift_regenerative_features': system.lift_regenerative_features,
                'vvvf_sleep_mode': system.vvvf_sleep_mode,
                'annual_energy_consumption_kwh': system.annual_energy_consumption_kwh,
            })

        return JsonResponse({
            'success': True,
            'lift_escalator_systems': systems_data
        }, status=200)

    except Exception as e:
        return JsonResponse({
            'success': False,
            'errors': {'server': [f'An unexpected error occurred: {str(e)}']}
        }, status=500)


@login_required
@require_http_methods(["DELETE"])
def delete_lift_escalator_system(request, system_id):
    """
    Delete a lift & escalator system.

    Returns:
    - Success: {"success": true, "message": str} (200)
    - Failure: {"success": false, "errors": dict} (400/404)
    """
    try:
        # Get lift & escalator system and check permissions
        try:
            lift_escalator_system = LiftEscalatorSystem.objects.get(
                id=system_id,
                building__created_by=request.user
            )
        except LiftEscalatorSystem.DoesNotExist:
            return JsonResponse({
                'success': False,
                'errors': {'system_id': ['Lift & escalator system not found or you do not have permission to delete it.']}
            }, status=404)

        # Delete the system
        with transaction.atomic():
            lift_escalator_system.delete()

        return JsonResponse({
            'success': True,
            'message': 'Lift & escalator system deleted successfully.'
        }, status=200)

    except Exception as e:
        return JsonResponse({
            'success': False,
            'errors': {'server': [f'An unexpected error occurred: {str(e)}']}
        }, status=500)