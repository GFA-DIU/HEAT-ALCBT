"""
API view for the full building detail page.

GET /api/buildings/<uuid>/detail/

Returns everything the HTMX building detail page shows:
  - Core building fields (same as AdminBuildingSerializer)
  - Full operational schedule & temperature settings
  - All operational systems (cooling, ventilation, lighting, lift, hot water)
  - All operational products (energy carriers)
  - All structural assemblies with their materials
  - Carbon statistics (footprint, embodied, operational, savings %)
  - Chart data (embodied by assembly, embodied by material, operational by system)
"""

import logging

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from api.permissions import IsAdminUser
from api.views.buildings import _buildings_queryset
from pages.models.building import Building
from pages.models.building_operation import (
    CoolingSystemAirConditioner, CoolingSystemChiller,
    HotWaterSystem, LiftEscalatorSystem,
)
from pages.models.building_operation.ventilation import VentilationSystem
from pages.models.building_operation.lighting import LightingSystem
from pages.views.building.building_stats import (
    calculate_total_carbon_footprint,
    calculate_total_embodied_carbon,
    calculate_total_operational_carbon,
    calculate_carbon_savings_percentage,
    get_embodied_carbon_by_assembly,
    get_embodied_carbon_by_material,
    get_operational_carbon_by_system,
)

logger = logging.getLogger(__name__)


def _serialize_chiller(s):
    return {
        "id": s.id,
        "cooling_system_type": "chiller",
        "chiller_type": s.chiller_type,
        "chiller_type_display": s.get_chiller_type_display(),
        "year_of_installation": s.year_of_installation,
        "refrigerant_type": s.refrigerant_type,
        "refrigerant_quantity_kg": s.refrigerant_quantity_kg,
        "variable_speed_drives": s.variable_speed_drives,
        "heat_recovery_system": s.heat_recovery_system,
        "total_cooling_load_rt": s.total_cooling_load_rt,
        "baseline_leakage_factor_percent": s.baseline_leakage_factor_percent,
        "operation_hours_per_workday": s.operation_hours_per_workday,
        "workdays_per_week": s.workdays_per_week,
        "workweeks_per_year": s.workweeks_per_year,
        "baseline_cooling_efficiency_kw_h": s.baseline_cooling_efficiency_kw_h,
        "number_of_chillers": s.number_of_chillers,
        "total_chiller_system_power_input_kw": s.total_chiller_system_power_input_kw,
        "water_cooled_chiller_cooling_load_factor_percent": s.water_cooled_chiller_cooling_load_factor_percent,
        "cop": float(s.cop) if s.cop else None,
        "ip_lv": float(s.ip_lv) if s.ip_lv else None,
        "energy_efficiency_label": s.energy_efficiency_label,
        "number_of_stars": s.number_of_stars,
        "total_energy_consumption_kwh_per_year": s.total_energy_consumption_kwh_per_year,
        "baseline_refrigerant_emission_factor": s.baseline_refrigerant_emission_factor,
    }


def _serialize_ac(s):
    return {
        "id": s.id,
        "cooling_system_type": "air_conditioner",
        "ac_type": s.ac_type,
        "ac_type_display": s.get_ac_type_display(),
        "packaged_subtype": s.packaged_subtype,
        "packaged_subtype_display": s.get_packaged_subtype_display() if s.packaged_subtype else None,
        "year_of_installation": s.year_of_installation,
        "refrigerant_type": s.refrigerant_type,
        "refrigerant_quantity_kg": s.refrigerant_quantity_kg,
        "number_of_units_installed": s.number_of_units_installed,
        "baseline_leakage_factor_percent": s.baseline_leakage_factor_percent,
        "operation_hours_per_workday": s.operation_hours_per_workday,
        "workdays_per_week": s.workdays_per_week,
        "workweeks_per_year": s.workweeks_per_year,
        "total_cooling_load_rt": s.total_cooling_load_rt,
        "total_power_input_kw": float(s.total_power_input_kw) if s.total_power_input_kw else None,
        "energy_efficiency_label": s.energy_efficiency_label,
        "number_of_stars": s.number_of_stars,
        "cop": float(s.cop) if s.cop else None,
        "ip_lv": float(s.ip_lv) if s.ip_lv else None,
        "total_energy_consumption_kwh_per_year": s.total_energy_consumption_kwh_per_year,
        "baseline_refrigerant_emission_factor": s.baseline_refrigerant_emission_factor,
    }


def _serialize_ventilation(s):
    return {
        "id": s.id,
        "ventilation_type": s.ventilation_type,
        "ventilation_type_display": s.get_ventilation_type_display(),
        "ventilation_capacity": s.ventilation_capacity,
        "ventilation_capacity_display": s.get_ventilation_capacity_display() if s.ventilation_capacity else None,
        "baseline_efficiency_w_cmh": float(s.baseline_efficiency_w_cmh) if s.baseline_efficiency_w_cmh else None,
        "operation_hours_per_workday": s.operation_hours_per_workday,
        "workdays_per_week": s.workdays_per_week,
        "workweeks_per_year": s.workweeks_per_year,
        "total_power_input_kw": float(s.total_power_input_kw) if s.total_power_input_kw else None,
        "air_flow_rate": s.air_flow_rate,
        "demand_controlled_ventilation": s.demand_controlled_ventilation,
        "variable_speed_drives": s.variable_speed_drives,
        "number_of_units_installed": s.number_of_units_installed,
        "total_energy_consumption_kwh_per_year": s.total_energy_consumption_kwh_per_year,
        "fresh_air_ratio_percent": s.fresh_air_ratio_percent,
        "number_of_stars": s.number_of_stars,
    }


def _serialize_lighting(s):
    return {
        "id": s.id,
        "room_type": s.room_type,
        "room_type_display": s.get_room_type_display(),
        "area_of_room": s.area_of_room,
        "lighting_bulb_type": s.lighting_bulb_type,
        "lighting_bulb_type_display": s.get_lighting_bulb_type_display(),
        "number_of_bulbs": s.number_of_bulbs,
        "tubes_per_fixture": s.tubes_per_fixture,
        "light_bulb_power_rating_w": s.light_bulb_power_rating_w,
        "total_lighting_power_kw": float(s.total_lighting_power_kw) if s.total_lighting_power_kw is not None else None,
        "baseline_lighting_power_density": float(s.baseline_lighting_power_density) if s.baseline_lighting_power_density is not None else None,
        "operation_hours_per_workday": s.operation_hours_per_workday,
        "workdays_per_week": s.workdays_per_week,
        "workweeks_per_year": s.workweeks_per_year,
        "sensors_installed": s.sensors_installed,
        "total_energy_consumption_kwh_per_year": s.total_energy_consumption_kwh_per_year,
        "energy_efficiency_label": s.energy_efficiency_label,
        "energy_efficiency_label_display": s.get_energy_efficiency_label_display() if s.energy_efficiency_label else None,
        "number_of_stars": s.number_of_stars,
    }


def _serialize_lift(s):
    return {
        "id": s.id,
        "number_of_lifts": s.number_of_lifts,
        "lift_regenerative_features": s.lift_regenerative_features,
        "vvvf_sleep_mode": s.vvvf_sleep_mode,
        "annual_energy_consumption_kwh": s.annual_energy_consumption_kwh,
    }


def _serialize_hot_water(s):
    return {
        "id": s.id,
        "type_of_hot_water_system": s.type_of_hot_water_system,
        "type_of_hot_water_system_display": s.get_type_of_hot_water_system_display(),
        "fuel_type": s.fuel_type,
        "fuel_type_display": s.get_fuel_type_display(),
        "number_of_equipment": s.number_of_equipment,
        "operating_hours_per_day": str(s.operating_hours_per_day),
        "operating_days_per_week": s.operating_days_per_week,
        "operating_weeks_per_year": s.operating_weeks_per_year,
        "baseline_efficiency": str(s.baseline_efficiency),
        "heat_recovery_system": s.heat_recovery_system,
        "equipment_efficiency_level": str(s.equipment_efficiency_level),
        "power_input": str(s.power_input) if s.power_input is not None else None,
        "total_energy_consumption_kwh_per_year": s.total_energy_consumption_kwh_per_year,
        "total_fuel_consumption": str(s.total_fuel_consumption) if s.total_fuel_consumption is not None else None,
        "fuel_consumption_unit": s.fuel_consumption_unit,
    }


def _serialize_operational_product(op):
    return {
        "id": op.id,
        "epd": {
            "id": str(op.epd.pk),
            "name": op.epd.name,
            "declared_unit": op.epd.declared_unit,
            "country": op.epd.country.name if op.epd.country else None,
        } if op.epd else None,
        "quantity": float(op.quantity) if op.quantity else None,
        "input_unit": op.input_unit,
        "description": op.description,
    }


def _serialize_assembly(ba):
    """Serialize a BuildingAssembly with its Assembly and materials."""
    assembly = ba.assembly
    materials = []
    for sp in assembly.structuralproduct_set.select_related("epd", "classification__category", "classification__technique").all():
        materials.append({
            "id": sp.id,
            "epd": {
                "id": str(sp.epd.pk),
                "name": sp.epd.name,
                "declared_unit": sp.epd.declared_unit,
                "country": sp.epd.country.name if sp.epd.country else None,
            } if sp.epd else None,
            "quantity": float(sp.quantity) if sp.quantity else None,
            "input_unit": sp.input_unit,
            "classification": {
                "category": str(sp.classification.category) if sp.classification and sp.classification.category else None,
                "technique": str(sp.classification.technique) if sp.classification and sp.classification.technique else None,
            } if sp.classification else None,
        })
    return {
        "building_assembly_id": ba.id,
        "assembly_id": assembly.id,
        "name": assembly.name,
        "comment": assembly.comment,
        "dimension": assembly.dimension,
        "quantity": float(ba.quantity) if ba.quantity else None,
        "reporting_life_cycle": ba.reporting_life_cycle,
        "materials": materials,
    }


class BuildingFullDetailView(APIView):
    """
    GET /api/buildings/<uuid>/detail/

    Returns the full building detail: core info, all systems, operational
    products, structural assemblies, carbon statistics and chart data.
    """
    permission_classes = [IsAdminUser]

    def get(self, request, pk):
        try:
            building = _buildings_queryset(request).get(pk=pk)
        except Building.DoesNotExist:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)

        # Core fields
        core = {
            "id": str(building.pk),
            "uuid": str(building.uuid),
            "name": building.name,
            "street": building.street or "",
            "country": {"id": building.country_id, "name": building.country.name} if building.country else None,
            "region": {"id": building.region_id, "name": building.region.name} if building.region else None,
            "city": {"id": building.city_id, "name": building.city.name} if building.city else None,
            "longitude": building.longitude,
            "latitude": building.latitude,
            "climate_zone": {"id": building.climate_zone.id, "name": building.climate_zone.name} if building.climate_zone else None,
            "total_floor_area": str(building.total_floor_area),
            "cond_floor_area": str(building.cond_floor_area) if building.cond_floor_area else None,
            "floors_below_ground": building.floors_below_ground,
            "construction_year": building.construction_year,
            "reference_period": building.reference_period,
            "category": {
                "category_id": building.category.category_id,
                "category_name": building.category.category.name if building.category.category else None,
                "subcategory_id": building.category.subcategory_id,
                "subcategory_name": building.category.subcategory.name if building.category.subcategory else None,
            } if building.category else None,
            "created_at": building.created_at.isoformat() if building.created_at else None,
            "created_by": {
                "id": str(building.created_by.id),
                "name": building.created_by.get_full_name() or building.created_by.username,
            } if building.created_by else None,
            "organisation": {
                "id": str(building.organisation.pk),
                "name": building.organisation.name,
            } if building.organisation else None,
            "draft": building.draft,
            "public": building.public,
            "has_certification": building.has_certification,
            "has_boq": building.has_boq,
        }

        # Operational schedule
        schedule = {
            "num_residents": building.num_residents,
            "hours_per_workday": building.hours_per_workday,
            "workdays_per_week": building.workdays_per_week,
            "weeks_per_year": building.weeks_per_year,
            "heating_temp": float(building.heating_temp) if building.heating_temp else None,
            "heating_temp_unit": building.heating_temp_unit,
            "cooling_temp": float(building.cooling_temp) if building.cooling_temp else None,
            "cooling_temp_unit": building.cooling_temp_unit,
            "renewable_energy_percent": float(building.renewable_energy_percent) if building.renewable_energy_percent else None,
            "building_smart_system": building.building_smart_system,
        }

        # Operational systems
        cooling_systems = (
            [_serialize_chiller(s) for s in CoolingSystemChiller.objects.filter(building=building).order_by("id")] +
            [_serialize_ac(s) for s in CoolingSystemAirConditioner.objects.filter(building=building).order_by("id")]
        )
        ventilation_systems = [_serialize_ventilation(s) for s in VentilationSystem.objects.filter(building=building).order_by("id")]
        lighting_systems = [_serialize_lighting(s) for s in LightingSystem.objects.filter(building=building).order_by("id")]
        lift_systems = [_serialize_lift(s) for s in LiftEscalatorSystem.objects.filter(building=building)]
        hot_water_systems = [_serialize_hot_water(s) for s in HotWaterSystem.objects.filter(building=building).order_by("id")]

        # Operational products
        operational_products = [
            _serialize_operational_product(op)
            for op in building.operational_products.select_related("epd__country").all()
        ]

        # Structural assemblies
        structural_components = [
            _serialize_assembly(ba)
            for ba in building.buildingassembly_set.select_related("assembly").prefetch_related(
                "assembly__structuralproduct_set__epd__country",
                "assembly__structuralproduct_set__classification__category",
                "assembly__structuralproduct_set__classification__technique",
            ).order_by("-assembly__created_at")
        ]

        # Carbon statistics
        try:
            embodied = calculate_total_embodied_carbon(building, simulated=False)
            operational_carbon = calculate_total_operational_carbon(building, simulated=False)
            stats = {
                "total_carbon_footprint": float(embodied + operational_carbon),
                "total_embodied_carbon": float(embodied),
                "total_operational_carbon": float(operational_carbon),
                "carbon_savings_percentage": float(calculate_carbon_savings_percentage(building)),
            }
        except Exception:
            stats = {
                "total_carbon_footprint": None,
                "total_embodied_carbon": None,
                "total_operational_carbon": None,
                "carbon_savings_percentage": None,
            }

        # Chart data
        try:
            chart_data = {
                "embodied_by_assembly": get_embodied_carbon_by_assembly(building),
                "embodied_by_material": get_embodied_carbon_by_material(building),
                "operational_by_system": get_operational_carbon_by_system(building),
            }
        except Exception:
            chart_data = {}

        return Response({
            **core,
            "schedule": schedule,
            "cooling_systems": cooling_systems,
            "ventilation_systems": ventilation_systems,
            "lighting_systems": lighting_systems,
            "lift_systems": lift_systems,
            "hot_water_systems": hot_water_systems,
            "operational_products": operational_products,
            "structural_components": structural_components,
            "stats": stats,
            "chart_data": chart_data,
        })
