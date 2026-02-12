import json
import uuid as uuid_lib
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from django.db import transaction

from pages.models.building import Building
from pages.models.building_operation import HotWaterSystem
from pages.forms.hot_water_system_form import HotWaterSystemForm


def get_building_by_uuid(building_uuid, user):
    try:
        uuid_obj = uuid_lib.UUID(str(building_uuid))
        return Building.objects.get(uuid=uuid_obj, created_by=user)
    except (ValueError, AttributeError) as e:
        raise ValueError(f"Invalid UUID format: {building_uuid}")


def _serialize(system):
    return {
        'id': system.id,
        'type_of_hot_water_system': system.type_of_hot_water_system,
        'type_of_hot_water_system_display': system.get_type_of_hot_water_system_display(),
        'fuel_type': system.fuel_type,
        'fuel_type_display': system.get_fuel_type_display(),
        'number_of_equipment': system.number_of_equipment,
        'operating_hours_per_day': str(system.operating_hours_per_day),
        'operating_days_per_week': system.operating_days_per_week,
        'operating_weeks_per_year': system.operating_weeks_per_year,
        'baseline_efficiency': str(system.baseline_efficiency),
        'heat_recovery_system': system.heat_recovery_system,
        'equipment_efficiency_level': str(system.equipment_efficiency_level),
        'power_input': str(system.power_input) if system.power_input is not None else None,
        'total_energy_consumption_kwh_per_year': system.total_energy_consumption_kwh_per_year,
    }


@login_required
@require_http_methods(["POST", "PUT"])
def create_or_update_hot_water_system(request):
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

        hot_water_system_id = data.get('hot_water_system_id')
        is_update = bool(hot_water_system_id)

        if is_update:
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
            form = HotWaterSystemForm(data)

        if form.is_valid():
            with transaction.atomic():
                hot_water_system = form.save(commit=False)
                hot_water_system.building = building
                hot_water_system.save()

            return JsonResponse({
                'success': True,
                'message': 'Hot water system updated successfully.' if is_update else 'Hot water system created successfully.',
                'hot_water_system': _serialize(hot_water_system),
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
def get_hot_water_systems(request, building_uuid):
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

        hot_water_systems = HotWaterSystem.objects.filter(building=building).order_by('-id')

        return JsonResponse({
            'success': True,
            'hot_water_systems': [_serialize(s) for s in hot_water_systems],
        }, status=200)

    except Exception as e:
        return JsonResponse({
            'success': False,
            'errors': {'server': [f'An unexpected error occurred: {str(e)}']}
        }, status=500)


@login_required
@require_http_methods(["DELETE"])
def delete_hot_water_system(request, system_id):
    try:
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