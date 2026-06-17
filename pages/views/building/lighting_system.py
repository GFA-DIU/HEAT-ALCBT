import json
import uuid as uuid_lib
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from django.db import transaction

from pages.models.building import Building
from pages.models.building_operation import LightingSystem
from pages.forms.lighting_system_form import LightingSystemForm


def get_building_by_uuid(building_uuid, user):
    try:
        uuid_obj = uuid_lib.UUID(str(building_uuid))
        return Building.objects.get(uuid=uuid_obj, created_by=user)
    except (ValueError, AttributeError) as e:
        raise ValueError(f"Invalid UUID format: {building_uuid}")


def _serialize(system):
    return {
        'id': system.id,
        'room_type': system.room_type,
        'room_type_display': system.get_room_type_display(),
        'area_of_room': system.area_of_room,
        'lighting_bulb_type': system.lighting_bulb_type,
        'lighting_bulb_type_display': system.get_lighting_bulb_type_display(),
        'number_of_bulbs': system.number_of_bulbs,
        'tubes_per_fixture': system.tubes_per_fixture,
        'light_bulb_power_rating_w': system.light_bulb_power_rating_w,
        'total_lighting_power_kw': float(system.total_lighting_power_kw) if system.total_lighting_power_kw is not None else None,
        'baseline_lighting_power_density': float(system.baseline_lighting_power_density) if system.baseline_lighting_power_density is not None else None,
        'operation_hours_per_workday': system.operation_hours_per_workday,
        'workdays_per_week': system.workdays_per_week,
        'workweeks_per_year': system.workweeks_per_year,
        'sensors_installed': system.sensors_installed,
        'total_energy_consumption_kwh_per_year': system.total_energy_consumption_kwh_per_year,
        'energy_efficiency_label': system.energy_efficiency_label,
        'energy_efficiency_label_display': system.get_energy_efficiency_label_display() if system.energy_efficiency_label else None,
        'number_of_stars': system.number_of_stars,
    }


@login_required
@require_http_methods(["POST", "PUT"])
def create_or_update_lighting_system(request):
    try:
        data = json.loads(request.body)

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

        lighting_system_id = data.get('lighting_system_id')
        is_update = bool(lighting_system_id)

        if is_update:
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
            form = LightingSystemForm(data)

        if form.is_valid():
            with transaction.atomic():
                lighting_system = form.save(commit=False)
                lighting_system.building = building
                lighting_system.save()

            return JsonResponse({
                'success': True,
                'message': 'Lighting system updated successfully.' if is_update else 'Lighting system created successfully.',
                'lighting_system': _serialize(lighting_system),
            }, status=200 if is_update else 201)
        else:
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
def get_lighting_systems(request, building_uuid):
    try:
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

        lighting_systems = LightingSystem.objects.filter(building=building).order_by('-id')

        return JsonResponse({
            'success': True,
            'lighting_systems': [_serialize(s) for s in lighting_systems],
            'not_applicable': building.lighting_not_applicable,
        }, status=200)

    except Exception as e:
        return JsonResponse({
            'success': False,
            'errors': {'server': [f'An unexpected error occurred: {str(e)}']}
        }, status=500)


@login_required
@require_http_methods(["DELETE"])
def delete_lighting_system(request, system_id):
    try:
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