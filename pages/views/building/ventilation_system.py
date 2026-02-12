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
    try:
        uuid_obj = uuid_lib.UUID(str(building_uuid))
        return Building.objects.get(uuid=uuid_obj, created_by=user)
    except (ValueError, AttributeError):
        raise ValueError(f"Invalid UUID format: {building_uuid}")


def _serialize(system):
    return {
        'id': system.id,
        'ventilation_type': system.ventilation_type,
        'ventilation_type_display': system.get_ventilation_type_display(),
        'ventilation_capacity': system.ventilation_capacity,
        'ventilation_capacity_display': system.get_ventilation_capacity_display() if system.ventilation_capacity else None,
        'baseline_efficiency_w_cmh': float(system.baseline_efficiency_w_cmh) if system.baseline_efficiency_w_cmh else None,
        'operation_hours_per_workday': system.operation_hours_per_workday,
        'workdays_per_week': system.workdays_per_week,
        'workweeks_per_year': system.workweeks_per_year,
        'total_power_input_kw': float(system.total_power_input_kw) if system.total_power_input_kw else None,
        'air_flow_rate': system.air_flow_rate,
        'demand_controlled_ventilation': system.demand_controlled_ventilation,
        'variable_speed_drives': system.variable_speed_drives,
        'number_of_units_installed': system.number_of_units_installed,
        'total_energy_consumption_kwh_per_year': system.total_energy_consumption_kwh_per_year,
        'fresh_air_ratio_percent': system.fresh_air_ratio_percent,
        'number_of_stars': system.number_of_stars,
    }


@login_required
@require_http_methods(["POST", "PUT"])
def create_or_update_ventilation_system(request):
    try:
        data = json.loads(request.body)

        building_uuid = data.get('building_uuid')
        if not building_uuid:
            return JsonResponse({'success': False, 'errors': {'building_uuid': ['Building UUID is required.']}}, status=400)

        try:
            building = get_building_by_uuid(building_uuid, request.user)
        except ValueError as e:
            return JsonResponse({'success': False, 'errors': {'building_uuid': [str(e)]}}, status=400)
        except Building.DoesNotExist:
            return JsonResponse({'success': False, 'errors': {'building_uuid': ['Building not found.']}}, status=404)

        ventilation_system_id = data.get('ventilation_system_id')
        is_update = bool(ventilation_system_id)

        if is_update:
            try:
                ventilation_system = VentilationSystem.objects.get(id=ventilation_system_id, building=building)
            except VentilationSystem.DoesNotExist:
                return JsonResponse({'success': False, 'errors': {'ventilation_system_id': ['Ventilation system not found.']}}, status=404)
            form = VentilationSystemForm(data, instance=ventilation_system)
        else:
            form = VentilationSystemForm(data)

        if form.is_valid():
            with transaction.atomic():
                ventilation_system = form.save(commit=False)
                ventilation_system.building = building
                ventilation_system.save()

            return JsonResponse({
                'success': True,
                'message': 'Ventilation system updated successfully.' if is_update else 'Ventilation system created successfully.',
                'ventilation_system': _serialize(ventilation_system),
            }, status=200 if is_update else 201)
        else:
            return JsonResponse({'success': False, 'errors': form.errors}, status=400)

    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'errors': {'json': ['Invalid JSON payload.']}}, status=400)
    except Exception as e:
        return JsonResponse({'success': False, 'errors': {'server': [f'An unexpected error occurred: {str(e)}']}}, status=500)


@login_required
@require_http_methods(["GET"])
def get_ventilation_systems(request, building_uuid):
    try:
        try:
            building = get_building_by_uuid(building_uuid, request.user)
        except ValueError as e:
            return JsonResponse({'success': False, 'errors': {'building_uuid': [str(e)]}}, status=400)
        except Building.DoesNotExist:
            return JsonResponse({'success': False, 'errors': {'building_uuid': ['Building not found.']}}, status=404)

        systems = VentilationSystem.objects.filter(building=building).order_by('-id')
        return JsonResponse({'success': True, 'ventilation_systems': [_serialize(s) for s in systems]}, status=200)

    except Exception as e:
        return JsonResponse({'success': False, 'errors': {'server': [f'An unexpected error occurred: {str(e)}']}}, status=500)


@login_required
@require_http_methods(["DELETE"])
def delete_ventilation_system(request, system_id):
    try:
        try:
            ventilation_system = VentilationSystem.objects.get(id=system_id, building__created_by=request.user)
        except VentilationSystem.DoesNotExist:
            return JsonResponse({'success': False, 'errors': {'system_id': ['Ventilation system not found.']}}, status=404)

        with transaction.atomic():
            ventilation_system.delete()

        return JsonResponse({'success': True, 'message': 'Ventilation system deleted successfully.'}, status=200)

    except Exception as e:
        return JsonResponse({'success': False, 'errors': {'server': [f'An unexpected error occurred: {str(e)}']}}, status=500)