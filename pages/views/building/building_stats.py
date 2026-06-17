"""
Utility functions for calculating building statistics.

This module provides functions to calculate dynamic statistics for buildings:
- Progress percentage (based on data completion)
- Total carbon footprint (structural + operational)
- Total embodied carbon (structural components only)
- Total operational carbon (operational products only)
- Carbon savings (comparison between simulated and actual)
- Chart data for visualizations (by assembly, material, system)
"""

import json
import os
from collections import defaultdict
from decimal import Decimal
from typing import Dict, Any, List, Optional

from pages.models.building import Building
from pages.models.epd import Unit
from pages.views.building.embodied_benchmark_data import get_embodied_savings_data
from pages.models.building_operation.air_conditioning import CoolingSystemAirConditioner
from pages.models.building_operation.chilling import CoolingSystemChiller
from pages.models.building_operation.ventilation import VentilationSystem
from pages.models.building_operation.lighting import LightingSystem
from pages.models.building_operation.general_systems import LiftEscalatorSystem
from pages.models.building_operation.hot_water import HotWaterSystem
from pages.views.building.impact_calculation import calculate_impacts, calculate_impact_operational, ImpactCalculationError

_MAPPING_PATH = os.path.join(
    os.path.dirname(__file__),
    "building_dashboard",
    "material_category_mapping.json",
)
with open(_MAPPING_PATH, "r") as _f:
    _MATERIAL_CATEGORY_MAPPING = json.load(_f)


def calculate_progress_percentage(building: Building) -> int:
    """
    Calculate the percentage of building data completion based on the 10-step creation flow.

    Progress is calculated based on which steps have been completed:
    - Step 1.1 (Building Name & Location): 10%
    - Step 1.2 (Building Details): 10%
    - Step 2.1 (Operational Schedule): 10%
    - Step 2.2-2.6 (Systems: Cooling, Ventilation, Lighting, Lift, Hot Water): 10% each (50% total)
    - Step 3 (Operational Data Entry): 10%
    - Step 4 (Structural Components): 10%

    Args:
        building: Building instance to calculate progress for

    Returns:
        Integer percentage from 0 to 100
    """
    progress = 0

    # Step 1.1: Building Name & Location (10%)
    if building.name and building.address and building.country:
        progress += 10

    # Step 1.2: Building Details (10%)
    if building.category and building.total_floor_area:
        progress += 10

    # Step 2.1: Operational Schedule & Temperature (10%)
    if (building.num_residents is not None and
        building.hours_per_workday is not None and
        building.workdays_per_week is not None and
        building.weeks_per_year is not None and
        building.heating_temp is not None and
        building.cooling_temp is not None):
        progress += 10

    # Step 2.2: Cooling System (10%)
    if building.air_conditioners.exists() or building.chillers.exists():
        progress += 10

    # Step 2.3: Ventilation System (10%)
    if building.ventilation_systems.exists():
        progress += 10

    # Step 2.4: Lighting System (10%)
    if building.lighting_systems.exists():
        progress += 10

    # Step 2.5: Lift & Escalator System (10%)
    if building.lift_escalator_systems.exists():
        progress += 10

    # Step 2.6: Hot Water System (10%)
    if building.hot_water_systems.exists():
        progress += 10

    # Step 3: Operational Data Entry (10%)
    # Check if at least one operational product (energy carrier) has been added
    operational_count = building.operational_products.count()
    if operational_count > 0:
        progress += 10

    # Step 4: Structural Components (10%)
    # Check if at least one structural assembly has been added
    structural_count = building.buildingassembly_set.count()
    if structural_count > 0:
        progress += 10

    return min(progress, 100)  # Cap at 100%


def calculate_total_embodied_carbon(
    building: Building,
    simulated: bool = False,
    prefetched_assemblies=None,
    calculation_errors: Optional[list] = None,
) -> Decimal:
    """
    Calculate total embodied carbon (GWP A1-A3) from structural components.

    Args:
        building: Building instance to calculate for
        simulated: If True, calculate for simulated components; if False, for actual components
        prefetched_assemblies: Optional pre-fetched BuildingAssembly queryset/list to avoid re-querying
        calculation_errors: Optional list to append (assembly_name, epd_name, reason) tuples for skipped products

    Returns:
        Total embodied carbon in kgCO2e/m² (normalized by floor area)
    """
    total_gwp = Decimal('0.0')

    if prefetched_assemblies is not None:
        building_assemblies = prefetched_assemblies
    elif simulated:
        building_assemblies = building.buildingassemblysimulated_set.all()
    else:
        building_assemblies = building.buildingassembly_set.all()

    for ba in building_assemblies:
        assembly = ba.assembly
        assembly_quantity = ba.quantity
        products = getattr(assembly, "prefetched_products", None)
        if products is None:
            products = assembly.structuralproduct_set.all()

        for structural_product in products:
            try:
                impacts = calculate_impacts(
                    dimension=assembly.dimension,
                    assembly_quantity=assembly_quantity,
                    total_floor_area=float(building.total_floor_area),
                    p=structural_product
                )

                for impact in impacts:
                    if impact['impact_type'].impact_category == 'gwp' and \
                       impact['impact_type'].life_cycle_stage == 'a1a3':
                        value = Decimal(str(impact['impact_value']))
                        if value > 0:
                            total_gwp += value

            except (ImpactCalculationError, ValueError, AttributeError, ZeroDivisionError) as e:
                if calculation_errors is not None:
                    epd_name = getattr(getattr(structural_product, 'epd', None), 'name', 'Unknown EPD')
                    calculation_errors.append({
                        'assembly': assembly.name or 'Unknown assembly',
                        'epd': epd_name,
                        'reason': str(e),
                    })
                continue

    return total_gwp


def calculate_total_operational_carbon(
    building: Building,
    simulated: bool = False,
    prefetched_operational=None,
) -> Decimal:
    """
    Calculate total operational carbon (GWP B6) from operational products.

    Args:
        building: Building instance to calculate for
        simulated: If True, calculate for simulated products; if False, for actual products
        prefetched_operational: Optional pre-fetched operational product list to avoid re-querying

    Returns:
        Total operational carbon in kgCO2e/m² (normalized by floor area)
    """
    total_gwp_b6 = Decimal('0.0')

    if prefetched_operational is not None:
        operational_products = prefetched_operational
    elif simulated:
        operational_products = building.simulated_operational_products.all()
    else:
        operational_products = building.operational_products.all()

    reference_period = Decimal(str(building.reference_period))

    for op in operational_products:
        try:
            impacts = calculate_impact_operational(op)
            total_gwp_b6 += impacts.get('gwp_b6', Decimal('0.0')) * reference_period
        except (ValueError, AttributeError, ZeroDivisionError):
            continue

    return total_gwp_b6


def calculate_total_carbon_footprint(
    building: Building,
    simulated: bool = False,
    prefetched_assemblies=None,
    prefetched_operational=None,
) -> Decimal:
    """
    Calculate total carbon footprint (embodied + operational).

    Args:
        building: Building instance to calculate for
        simulated: If True, calculate for simulated components; if False, for actual components
        prefetched_assemblies: Optional pre-fetched assembly list
        prefetched_operational: Optional pre-fetched operational product list

    Returns:
        Total carbon footprint in kgCO2e/m²
    """
    embodied = calculate_total_embodied_carbon(
        building, simulated=simulated, prefetched_assemblies=prefetched_assemblies
    )
    operational = calculate_total_operational_carbon(
        building, simulated=simulated, prefetched_operational=prefetched_operational
    )
    return embodied + operational


def calculate_carbon_savings_percentage(building: Building) -> Decimal:
    """
    Calculate carbon savings percentage by comparing simulated (baseline) vs actual building.

    Savings % = ((Simulated Carbon - Actual Carbon) / Simulated Carbon) * 100

    If savings is negative, it means the actual building has more carbon than the baseline.
    If there are no simulated components, returns 0.

    Args:
        building: Building instance to calculate savings for

    Returns:
        Savings percentage as a Decimal (e.g., 15.5 for 15.5%)
    """
    # Check if building has simulated components
    has_simulated_structural = building.buildingassemblysimulated_set.exists()
    has_simulated_operational = building.simulated_operational_products.exists()

    if not (has_simulated_structural or has_simulated_operational):
        # No baseline to compare against
        return Decimal('0.0')

    # Calculate simulated (baseline) carbon
    simulated_carbon = calculate_total_carbon_footprint(building, simulated=True)

    # Calculate actual carbon
    actual_carbon = calculate_total_carbon_footprint(building, simulated=False)

    # Avoid division by zero
    if simulated_carbon == 0:
        return Decimal('0.0')

    # Calculate savings percentage
    savings = ((simulated_carbon - actual_carbon) / simulated_carbon) * 100

    return savings


def get_building_statistics(building: Building) -> Dict[str, Any]:
    """
    Get all statistics for a building in one call.

    Args:
        building: Building instance to calculate statistics for

    Returns:
        Dictionary containing all building statistics:
        - progress_percentage: int (0-100)
        - total_carbon_footprint: Decimal (kgCO2e/m²)
        - total_embodied_carbon: Decimal (kgCO2e/m²)
        - carbon_savings_percentage: Decimal (%)
    """
    return {
        'progress_percentage': calculate_progress_percentage(building),
        'total_carbon_footprint': calculate_total_carbon_footprint(building, simulated=False),
        'total_embodied_carbon': calculate_total_embodied_carbon(building, simulated=False),
        'carbon_savings_percentage': calculate_carbon_savings_percentage(building),
    }


# ============================================================================
# Building Detail Page Statistics and Chart Data
# ============================================================================

def get_building_detail_statistics(
    building: Building,
    prefetched_assemblies=None,
    prefetched_operational=None,
) -> Dict[str, Any]:
    """
    Get all statistics for a building detail page.

    Args:
        building: Building instance to calculate statistics for
        prefetched_assemblies: Optional pre-fetched assembly list (avoids re-querying)
        prefetched_operational: Optional pre-fetched operational product list

    Returns:
        Dictionary containing all building statistics for detail page:
        - total_carbon_footprint: Decimal (kgCO2e/m²)
        - total_embodied_carbon: Decimal (kgCO2e/m²)
        - total_operational_carbon: Decimal (kgCO2e/m²)
        - carbon_savings_percentage: Decimal (%)
        - calculation_errors: list of dicts with assembly/epd/reason for skipped products
    """
    calculation_errors = []
    embodied = calculate_total_embodied_carbon(
        building,
        simulated=False,
        prefetched_assemblies=prefetched_assemblies,
        calculation_errors=calculation_errors,
    )
    operational = calculate_total_operational_carbon(
        building,
        simulated=False,
        prefetched_operational=prefetched_operational,
    )

    # Per-year operational carbon intensity by system (matches the Systems-tab chart).
    operational_by_system = get_operational_carbon_by_system(
        building, prefetched_operational=prefetched_operational
    )

    return {
        'total_carbon_footprint': embodied + operational,
        'total_embodied_carbon': embodied,
        'total_operational_carbon': operational,
        # Per-year intensity (sum of Systems-tab bars), so the stat card matches the chart.
        'operational_carbon_per_year': operational_by_system.get('total', 0),
        'grid_emission_factor': _derive_grid_emission_factor(
            building, prefetched_operational=prefetched_operational
        ),
        'carbon_savings_percentage': calculate_carbon_savings_percentage(building),
        'calculation_errors': calculation_errors,
    }


def get_embodied_carbon_by_assembly(
    building: Building,
    simulated: bool = False,
    prefetched_assemblies=None,
) -> Dict[str, Any]:
    """
    Calculate embodied carbon grouped by assembly classification.

    Args:
        building: Building instance to calculate for
        simulated: If True, calculate for simulated components
        prefetched_assemblies: Optional pre-fetched assembly list

    Returns:
        Dictionary with 'labels', 'data', 'absolute', and 'total' for chart rendering
    """
    carbon_by_assembly = defaultdict(Decimal)

    if prefetched_assemblies is not None:
        building_assemblies = prefetched_assemblies
    elif simulated:
        building_assemblies = building.buildingassemblysimulated_set.all()
    else:
        building_assemblies = building.buildingassembly_set.all()

    for ba in building_assemblies:
        assembly = ba.assembly
        assembly_quantity = ba.quantity
        products = getattr(assembly, "prefetched_products", None)
        if products is None:
            products = assembly.structuralproduct_set.all()

        for structural_product in products:
            try:
                impacts = calculate_impacts(
                    dimension=assembly.dimension,
                    assembly_quantity=assembly_quantity,
                    total_floor_area=float(building.total_floor_area),
                    p=structural_product
                )

                for impact in impacts:
                    if impact['impact_type'].impact_category == 'gwp' and \
                       impact['impact_type'].life_cycle_stage == 'a1a3':
                        value = Decimal(str(impact['impact_value']))
                        if value > 0:
                            assembly_category = impact.get('assembly_category', '')
                            if not assembly_category:
                                continue
                            full_label = str(assembly_category)
                            label = full_label.split("- ", 1)[1] if "- " in full_label else full_label
                            carbon_by_assembly[label] += value

            except (ImpactCalculationError, ValueError, AttributeError, ZeroDivisionError):
                continue

    sorted_items = sorted(carbon_by_assembly.items(), key=lambda x: x[1], reverse=True)
    total = sum(v for _, v in sorted_items) or Decimal('1')

    labels = []
    data = []
    absolute = []
    for label, value in sorted_items[:10]:
        labels.append(label)
        percentage = float((value / total) * 100)
        data.append(round(percentage, 1))
        absolute.append(round(float(value), 2))

    chart_total = round(float(sum(v for _, v in sorted_items)), 2)
    return {'labels': labels, 'data': data, 'absolute': absolute, 'total': chart_total}


def get_embodied_carbon_by_material(
    building: Building,
    simulated: bool = False,
    prefetched_assemblies=None,
) -> Dict[str, Any]:
    """
    Calculate embodied carbon grouped by material category.

    Args:
        building: Building instance to calculate for
        simulated: If True, calculate for simulated components
        prefetched_assemblies: Optional pre-fetched assembly list

    Returns:
        Dictionary with 'labels', 'data', 'absolute', and 'total' for chart rendering
    """
    carbon_by_material = defaultdict(Decimal)

    if prefetched_assemblies is not None:
        building_assemblies = prefetched_assemblies
    elif simulated:
        building_assemblies = building.buildingassemblysimulated_set.all()
    else:
        building_assemblies = building.buildingassembly_set.all()

    for ba in building_assemblies:
        assembly = ba.assembly
        assembly_quantity = ba.quantity
        products = getattr(assembly, "prefetched_products", None)
        if products is None:
            products = assembly.structuralproduct_set.all()

        for structural_product in products:
            try:
                original_category = (
                    str(structural_product.epd.category)
                    if structural_product.epd and structural_product.epd.category
                    else "Others"
                )
                material_category = _MATERIAL_CATEGORY_MAPPING.get(original_category, "Others")

                impacts = calculate_impacts(
                    dimension=assembly.dimension,
                    assembly_quantity=assembly_quantity,
                    total_floor_area=float(building.total_floor_area),
                    p=structural_product
                )

                for impact in impacts:
                    if impact['impact_type'].impact_category == 'gwp' and \
                       impact['impact_type'].life_cycle_stage == 'a1a3':
                        value = Decimal(str(impact['impact_value']))
                        if value > 0:
                            carbon_by_material[material_category] += value

            except (ImpactCalculationError, ValueError, AttributeError, ZeroDivisionError):
                continue

    sorted_items = sorted(carbon_by_material.items(), key=lambda x: x[1], reverse=True)
    total = sum(v for _, v in sorted_items) or Decimal('1')

    labels = []
    data = []
    absolute = []
    for label, value in sorted_items[:10]:
        labels.append(label)
        percentage = float((value / total) * 100)
        data.append(round(percentage, 1))
        absolute.append(round(float(value), 2))

    chart_total = round(float(sum(v for _, v in sorted_items)), 2)
    return {'labels': labels, 'data': data, 'absolute': absolute, 'total': chart_total}


def _derive_grid_emission_factor(building: Building, prefetched_operational=None) -> Decimal:
    """
    Derive the grid emission factor (kgCO2eq/kWh) from the building's electricity EPD.

    The factor equals the electricity EPD's B6 GWP value divided by its declared
    amount (i.e. the per-kWh carbon intensity used internally by
    ``calculate_impact_operational`` for the (kWh, kWh) case).

    No dedicated DB field exists for the grid factor; it is computed on the fly.

    Args:
        building: Building instance to derive the factor for
        prefetched_operational: Optional pre-fetched operational product list

    Returns:
        Grid emission factor as a Decimal (kgCO2eq/kWh), or Decimal('0') if no
        suitable electricity EPD is found.
    """
    if prefetched_operational is not None:
        operational_products = prefetched_operational
    else:
        operational_products = building.operational_products.all()

    def _is_electricity(op) -> bool:
        try:
            epd = op.epd
            if epd is None:
                return False
            # Primary: kWh-declared electricity entered in kWh
            if epd.declared_unit == Unit.KWH and op.input_unit == Unit.KWH:
                return True
            # Fallback: category name suggests electricity/energy/power
            category = getattr(epd, "category", None)
            name = (category.name_en or "").lower() if category else ""
            return any(token in name for token in ("electr", "energy", "power"))
        except AttributeError:
            return False

    electricity_product = next(
        (op for op in operational_products if _is_electricity(op)), None
    )
    if electricity_product is None:
        return Decimal("0")

    try:
        epd = electricity_product.epd
        impact_set = epd.epdimpact_set.filter(impact__life_cycle_stage="b6")
        gwp_b6 = next(
            (i.value for i in impact_set if i.impact.impact_category == "gwp"), None
        )
        if gwp_b6 is None or not epd.declared_amount:
            return Decimal("0")
        return Decimal(str(gwp_b6)) / Decimal(str(epd.declared_amount))
    except (AttributeError, ZeroDivisionError):
        return Decimal("0")


def get_operational_carbon_by_system(
    building: Building,
    simulated: bool = False,
    prefetched_operational=None,
) -> Dict[str, Any]:
    """
    Calculate operational carbon intensity (kgCO2eq/m²/yr) grouped by building system.

    Uses the structured per-system annual energy (EnergySummary) multiplied by the
    derived grid emission factor and normalised by gross floor area:

        Carbon_intensity_system = system_kWh * Grid_factor / Floor_area

    The result is a per-YEAR intensity (no reference-period multiplier). Systems
    with no entered (zero/blank) energy are excluded so their chart bar is hidden.

    Args:
        building: Building instance to calculate for
        simulated: Unused (kept for signature compatibility)
        prefetched_operational: Optional pre-fetched operational product list,
            used to derive the grid emission factor

    Returns:
        Dictionary with 'labels', 'data' (% share of total), 'absolute'
        (kgCO2eq/m²/yr) and 'total'. May include 'blocked' (floor area missing)
        or 'warning' (grid factor is zero).
    """
    empty = {'labels': [], 'data': [], 'absolute': [], 'total': 0}

    summary = getattr(building, 'energy_summary', None)
    if summary is None:
        return empty

    floor_area = building.total_floor_area
    if not floor_area or Decimal(str(floor_area)) == 0:
        return {**empty, 'blocked': True}

    grid_factor = _derive_grid_emission_factor(building, prefetched_operational)
    floor_area = Decimal(str(floor_area))

    # Labels must match the substrings used by the Systems-tab JS systemStyleMap.
    systems = [
        ("Cooling systems", summary.cooling_kwh),
        ("Ventilation systems", summary.ventilation_kwh),
        ("Lighting systems", summary.lighting_kwh),
        ("Lift & escalator", summary.lift_escalator_kwh),
        ("Hot Water Systems", summary.hot_water_kwh),
    ]

    intensity_by_system = []
    for label, kwh in systems:
        if kwh is None or Decimal(str(kwh)) <= 0:
            continue
        intensity = Decimal(str(kwh)) * grid_factor / floor_area
        intensity_by_system.append((label, intensity))

    if not intensity_by_system:
        return empty

    intensity_by_system.sort(key=lambda x: x[1], reverse=True)
    total = sum(value for _, value in intensity_by_system)

    labels = []
    data = []
    absolute = []
    for label, value in intensity_by_system:
        labels.append(label)
        percentage = float((value / total) * 100) if total > 0 else 0.0
        data.append(round(percentage, 1))
        absolute.append(round(float(value), 2))

    result = {
        'labels': labels,
        'data': data,
        'absolute': absolute,
        'total': round(float(total), 2),
    }
    if grid_factor == 0:
        result['warning'] = 'grid_factor_zero'
    return result


def get_operational_carbon_by_appliance(
    building: Building,
    prefetched_operational=None,
) -> Dict[str, Any]:
    """
    Calculate operational carbon intensity (kgCO2eq/m²/yr) per individual appliance record.

    Same formula as get_operational_carbon_by_system but broken down to individual
    system records (e.g. each AC unit, each lighting zone) rather than category totals.

    Returns dict with 'labels' (appliance display name), 'systemNames' (parent system),
    'data' (% share), 'absolute' (kgCO2eq/m²/yr), 'total'.
    """
    empty = {'labels': [], 'systemNames': [], 'data': [], 'absolute': [], 'total': 0}

    floor_area = building.total_floor_area
    if not floor_area or Decimal(str(floor_area)) == 0:
        return empty

    grid_factor = _derive_grid_emission_factor(building, prefetched_operational)
    floor_area = Decimal(str(floor_area))

    AC_LABEL = {
        'window': 'Window AC',
        'split': 'Split AC',
        'vrv': 'VRF system',
        'packaged': 'Packaged AC',
    }
    VENT_LABEL = {
        'AHU': 'AHU',
        'FCU': 'FCU',
        'CASSETTE_AC': 'Cassette AC',
        'DOAS': 'DOAS',
        'FAN': 'Fan',
    }
    HW_LABEL = {
        'heat-pump': 'Heat pump water heater',
        'boiler': 'Boiler',
        'solar': 'Solar water heater',
    }

    def _is_led(bulb):
        return str(bulb).upper().startswith('LED')

    appliances = []

    for ac in CoolingSystemAirConditioner.objects.filter(building=building):
        kwh = ac.total_energy_consumption_kwh_per_year
        if kwh and Decimal(str(kwh)) > 0:
            appliances.append((AC_LABEL.get(ac.ac_type, 'AC unit'), 'Cooling system', Decimal(str(kwh))))

    for ch in CoolingSystemChiller.objects.filter(building=building):
        kwh = ch.total_energy_consumption_kwh_per_year
        if kwh and Decimal(str(kwh)) > 0:
            appliances.append(('Chiller', 'Cooling system', Decimal(str(kwh))))

    for v in VentilationSystem.objects.filter(building=building):
        kwh = v.total_energy_consumption_kwh_per_year
        if kwh and Decimal(str(kwh)) > 0:
            appliances.append((VENT_LABEL.get(v.ventilation_type, 'Ventilation'), 'Ventilation system', Decimal(str(kwh))))

    for lt in LightingSystem.objects.filter(building=building):
        kwh = lt.total_energy_consumption_kwh_per_year
        if kwh and Decimal(str(kwh)) > 0:
            label = 'LED lighting' if _is_led(lt.lighting_bulb_type) else 'Fluorescent lighting'
            appliances.append((label, 'Lighting system', Decimal(str(kwh))))

    for lft in LiftEscalatorSystem.objects.filter(building=building):
        kwh = lft.annual_energy_consumption_kwh
        if kwh and Decimal(str(kwh)) > 0:
            appliances.append(('Lift', 'Lifts & Escalators', Decimal(str(kwh))))

    for hw in HotWaterSystem.objects.filter(building=building):
        kwh = hw.total_energy_consumption_kwh_per_year
        if kwh and Decimal(str(kwh)) > 0:
            appliances.append((HW_LABEL.get(hw.type_of_hot_water_system, 'Water heater'), 'Hot water system', Decimal(str(kwh))))

    if not appliances:
        return empty

    intensities = [(label, sys_name, kwh * grid_factor / floor_area) for label, sys_name, kwh in appliances]
    intensities.sort(key=lambda x: x[2], reverse=True)
    total = sum(v for _, _, v in intensities)

    labels, system_names, data, absolute = [], [], [], []
    for label, sys_name, value in intensities:
        labels.append(label)
        system_names.append(sys_name)
        data.append(round(float((value / total) * 100) if total > 0 else 0.0, 1))
        absolute.append(round(float(value), 2))

    return {
        'labels': labels,
        'systemNames': system_names,
        'data': data,
        'absolute': absolute,
        'total': round(float(total), 2),
    }


def get_building_chart_data(
    building: Building,
    prefetched_assemblies=None,
    prefetched_operational=None,
) -> Dict[str, Any]:
    """
    Get all chart data for a building detail page.

    Args:
        building: Building instance to get chart data for
        prefetched_assemblies: Optional pre-fetched assembly list (avoids re-querying)
        prefetched_operational: Optional pre-fetched operational product list

    Returns:
        Dictionary containing chart data for:
        - whole_life_carbon: data for doughnut chart (embodied vs operational)
        - embodied_by_assembly: data for bar chart by assembly
        - embodied_by_material: data for bar chart by material
        - operational_by_system: data for bar chart by system/appliance
    """
    embodied = calculate_total_embodied_carbon(
        building, simulated=False, prefetched_assemblies=prefetched_assemblies
    )
    operational = calculate_total_operational_carbon(
        building, simulated=False, prefetched_operational=prefetched_operational
    )

    embodied_by_material = get_embodied_carbon_by_material(
        building, prefetched_assemblies=prefetched_assemblies
    )

    return {
        'whole_life_carbon': {
            'labels': ['Operational carbon', 'Embodied carbon'],
            'data': [float(operational), float(embodied)],
        },
        'embodied_by_assembly': get_embodied_carbon_by_assembly(
            building, prefetched_assemblies=prefetched_assemblies
        ),
        'embodied_by_material': embodied_by_material,
        'embodied_savings': get_embodied_savings_data(embodied_by_material),
        'operational_by_system': get_operational_carbon_by_system(
            building, prefetched_operational=prefetched_operational
        ),
        'operational_by_appliance': get_operational_carbon_by_appliance(
            building, prefetched_operational=prefetched_operational
        ),
    }