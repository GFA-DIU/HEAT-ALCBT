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
from pages.views.building.operational_benchmark_data import (
    get_operational_benchmark_for_building,
    calculate_operational_benchmark_position,
)
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
    Calculate weighted building data completion percentage.

    Weights:
    - Building Name & Location + Building Details: 20% (10% each)
    - Operational Data Entry (energy carriers):    30%
    - Structural Components:                       40%
    - Operational Systems (5 systems × 2%):        10%
      Each system is complete if it has data OR the user confirmed N/A.

    Returns integer 0–100.
    """
    progress = 0

    if building.name and building.address and building.country:
        progress += 10
    if building.category and building.total_floor_area:
        progress += 10

    if building.operational_products.count() > 0:
        progress += 30

    if building.buildingassembly_set.count() > 0:
        progress += 40

    # Each system counts 2% — complete if it has data or user confirmed N/A
    if building.air_conditioners.exists() or building.chillers.exists() or building.cooling_not_applicable:
        progress += 2
    if building.ventilation_systems.exists() or building.ventilation_not_applicable:
        progress += 2
    if building.lighting_systems.exists() or building.lighting_not_applicable:
        progress += 2
    if building.lift_escalator_systems.exists() or building.lift_not_applicable:
        progress += 2
    if building.hot_water_systems.exists() or building.hot_water_not_applicable:
        progress += 2

    return min(progress, 100)


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


def _op_is_electricity(op) -> bool:
    """An operational product is grid electricity when both its EPD's declared
    unit and the entered input unit are kWh (matches the grid-EF heuristic)."""
    try:
        return op.epd.declared_unit == Unit.KWH and op.input_unit == Unit.KWH
    except Exception:
        return False


def _renewable_electricity_fraction(building: Building, operational_products=None) -> Decimal:
    """Fraction (0..1) of the building's electricity offset by on-site renewables.

    On-site renewables are electricity, so this only ever reduces the electricity
    carrier's carbon. Entered either as a percentage of electricity, or as kWh/yr
    (converted to a fraction of the building's total electricity carriers).
    """
    mode = getattr(building, "renewable_input_mode", None) or Building.RENEWABLE_INPUT_PERCENT

    if mode == Building.RENEWABLE_INPUT_KWH:
        renew = getattr(building, "renewable_energy_kwh", None)
        if not renew:
            return Decimal("0")
        if operational_products is None:
            operational_products = building.operational_products.all()
        electricity_kwh = Decimal("0")
        for op in operational_products:
            if _op_is_electricity(op) and op.quantity:
                electricity_kwh += Decimal(str(op.quantity))
        if electricity_kwh <= 0:
            return Decimal("0")
        fraction = Decimal(str(renew)) / electricity_kwh
    else:
        pct = getattr(building, "renewable_energy_percent", None)
        if not pct:
            return Decimal("0")
        fraction = Decimal(str(pct)) / Decimal("100")

    # Clamp to [0, 1] — a building can't offset more than 100% of its electricity.
    if fraction < 0:
        return Decimal("0")
    if fraction > 1:
        return Decimal("1")
    return fraction


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

    # On-site renewables offset grid electricity only.
    renewable_fraction = _renewable_electricity_fraction(building, operational_products)
    electricity_multiplier = Decimal('1') - renewable_fraction

    for op in operational_products:
        try:
            impacts = calculate_impact_operational(op)
            gwp_b6 = impacts.get('gwp_b6', Decimal('0.0'))
            if _op_is_electricity(op):
                gwp_b6 = gwp_b6 * electricity_multiplier
            total_gwp_b6 += gwp_b6 * reference_period
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
        # Annual energy-use intensity (EPI, kWh/m2/yr) — gross demand, for the toggle.
        'operational_energy_intensity': operational_by_system.get('total_energy', 0),
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
    empty = {'labels': [], 'data': [], 'absolute': [], 'absolute_energy': [], 'total': 0, 'total_energy': 0}

    summary = getattr(building, 'energy_summary', None)
    if summary is None:
        return empty

    floor_area = building.total_floor_area
    if not floor_area or Decimal(str(floor_area)) == 0:
        return {**empty, 'blocked': True}

    grid_factor = _derive_grid_emission_factor(building, prefetched_operational)
    floor_area = Decimal(str(floor_area))

    # On-site renewables offset grid electricity; every system here is electricity.
    electricity_multiplier = Decimal('1') - _renewable_electricity_fraction(building, prefetched_operational)

    # Labels must match the substrings used by the Systems-tab JS systemStyleMap.
    systems = [
        ("Cooling systems", summary.cooling_kwh),
        ("Ventilation systems", summary.ventilation_kwh),
        ("Lighting systems", summary.lighting_kwh),
        ("Lift & escalator", summary.lift_escalator_kwh),
        ("Hot Water Systems", summary.hot_water_kwh),
        ("Plug & equipment loads", summary.plug_load_kwh),
    ]

    # Track carbon intensity (kgCO2e/m2/yr, net of renewables) and energy intensity
    # (kWh/m2/yr, gross demand) per system. Percentage share is identical for both
    # because the grid factor and renewable multiplier are uniform across systems.
    intensity_by_system = []
    for label, kwh in systems:
        if kwh is None or Decimal(str(kwh)) <= 0:
            continue
        energy_intensity = Decimal(str(kwh)) / floor_area
        carbon_intensity = energy_intensity * grid_factor * electricity_multiplier
        intensity_by_system.append((label, carbon_intensity, energy_intensity))

    if not intensity_by_system:
        return empty

    intensity_by_system.sort(key=lambda x: x[1], reverse=True)
    total = sum(c for _, c, _ in intensity_by_system)
    total_energy = sum(e for _, _, e in intensity_by_system)

    labels = []
    data = []
    absolute = []
    absolute_energy = []
    for label, carbon_intensity, energy_intensity in intensity_by_system:
        labels.append(label)
        percentage = float((carbon_intensity / total) * 100) if total > 0 else 0.0
        data.append(round(percentage, 1))
        absolute.append(round(float(carbon_intensity), 2))
        absolute_energy.append(round(float(energy_intensity), 2))

    result = {
        'labels': labels,
        'data': data,
        'absolute': absolute,
        'absolute_energy': absolute_energy,
        'total': round(float(total), 2),
        'total_energy': round(float(total_energy), 2),
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
    empty = {'labels': [], 'systemNames': [], 'data': [], 'absolute': [], 'absolute_energy': [], 'total': 0, 'total_energy': 0}

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

    # Plug / equipment loads: a manual energy-summary category with no per-unit records.
    summary = getattr(building, 'energy_summary', None)
    if summary is not None and summary.plug_load_kwh and Decimal(str(summary.plug_load_kwh)) > 0:
        appliances.append(('Plug & equipment loads', 'Plug & equipment loads', Decimal(str(summary.plug_load_kwh))))

    if not appliances:
        return empty

    # On-site renewables offset grid electricity; all appliances here are electricity.
    electricity_multiplier = Decimal('1') - _renewable_electricity_fraction(building, prefetched_operational)
    rows = []
    for label, sys_name, kwh in appliances:
        energy_intensity = kwh / floor_area
        carbon_intensity = energy_intensity * grid_factor * electricity_multiplier
        rows.append((label, sys_name, carbon_intensity, energy_intensity))
    rows.sort(key=lambda x: x[2], reverse=True)
    total = sum(c for _, _, c, _ in rows)
    total_energy = sum(e for _, _, _, e in rows)

    labels, system_names, data, absolute, absolute_energy = [], [], [], [], []
    for label, sys_name, carbon_intensity, energy_intensity in rows:
        labels.append(label)
        system_names.append(sys_name)
        data.append(round(float((carbon_intensity / total) * 100) if total > 0 else 0.0, 1))
        absolute.append(round(float(carbon_intensity), 2))
        absolute_energy.append(round(float(energy_intensity), 2))

    return {
        'labels': labels,
        'systemNames': system_names,
        'data': data,
        'absolute': absolute,
        'absolute_energy': absolute_energy,
        'total': round(float(total), 2),
        'total_energy': round(float(total_energy), 2),
    }


# ---------------------------------------------------------------------------
# Layer 3 — optimisation measures, BMS, refrigerant (operational savings)
# ---------------------------------------------------------------------------

# Per-system optimisation measures (spec §6). Each entry:
#   key, label, description, saving % (of the system's remaining carbon), and the
#   model + boolean flag (or predicate) that marks it "already installed".
# ``installed_when`` is a callable(records) -> bool: True when the measure counts
# as already installed (shown ON + locked, zero additional saving). A measure is
# installed only when EVERY record of that system has it (spec §10); a system with
# no records reports False (shown available/OFF, install state unknown).
_SYSTEM_STYLE = {
    "Cooling systems": {"key": "cooling", "icon": "snowflake-fill", "color": "#3B82F6"},
    "Ventilation systems": {"key": "ventilation", "icon": "windy-fill", "color": "#22C55E"},
    "Lighting systems": {"key": "lighting", "icon": "lightbulb-line", "color": "#EAB308"},
    "Hot Water Systems": {"key": "hot_water", "icon": "fire-line", "color": "#EF4444"},
    "Lift & escalator": {"key": "lift", "icon": "stairs-line", "color": "#818CF8"},
}

# Natural (target) refrigerants for the Scope-1 transition, lowest GWP preferred.
_NATURAL_REFRIGERANTS = ["R-717", "R-744", "R-290"]


def _all_records_flagged(records, attr):
    """True when there is at least one record and every record has ``attr`` truthy."""
    records = list(records)
    if not records:
        return False
    return all(bool(getattr(r, attr, False)) for r in records)


def _measures_for_system(system_key, building):
    """Return the list of measures for a system with their already-installed state.

    Each measure dict: {key, label, description, pct (0-1), installed (bool)}.
    """
    if system_key == "cooling":
        chillers = list(building.chillers.all())
        acs = list(building.air_conditioners.all())
        cooling_records = chillers + acs
        # VSD flag exists on both chillers and ACs; heat recovery on chillers.
        vsd_installed = bool(cooling_records) and all(
            getattr(r, "variable_speed_drives", False) for r in cooling_records
        )
        hr_installed = _all_records_flagged(chillers, "heat_recovery_system")
        return [
            {"key": "cooling_vsd", "label": "VSD on compressors & fans",
             "description": "Apply where VSD not already installed",
             "pct": 0.20, "installed": vsd_installed},
            {"key": "cooling_hr", "label": "Heat recovery system",
             "description": "Reclaim waste heat from cooling plant",
             "pct": 0.30, "installed": hr_installed},
        ]
    if system_key == "ventilation":
        vents = list(building.ventilation_systems.all())
        return [
            {"key": "vent_dcv", "label": "Demand-controlled ventilation (DCV)",
             "description": "Modulate airflow via occupancy & CO₂ sensors",
             "pct": 0.30, "installed": _all_records_flagged(vents, "demand_controlled_ventilation")},
            {"key": "vent_vsd", "label": "VSD on AHU & FCU fans",
             "description": "Variable speed drives on air handling units",
             "pct": 0.20, "installed": _all_records_flagged(vents, "variable_speed_drives")},
        ]
    if system_key == "lighting":
        lights = list(building.lighting_systems.all())
        all_led = bool(lights) and all(
            (l.lighting_bulb_type or "").startswith("LED_") for l in lights
        )
        return [
            {"key": "light_led", "label": "LED retrofit on fluorescent zones",
             "description": "Replace remaining fluorescent fixtures with LED equivalents",
             "pct": 0.40, "installed": all_led},
            {"key": "light_sensors", "label": "Occupancy & daylight sensors",
             "description": "Auto-switch lighting based on presence and natural light",
             "pct": 0.20, "installed": _all_records_flagged(lights, "sensors_installed")},
        ]
    if system_key == "hot_water":
        hw = list(building.hot_water_systems.all())
        all_heat_pump = bool(hw) and all(
            r.type_of_hot_water_system == "heat-pump" for r in hw
        )
        return [
            {"key": "hw_heatpump", "label": "Heat-pump water heater",
             "description": "Replace electric resistance with air-source heat pump",
             "pct": 0.50, "installed": all_heat_pump},
        ]
    if system_key == "lift":
        lifts = list(building.lift_escalator_systems.all())
        return [
            {"key": "lift_regen", "label": "Regenerative drives",
             "description": "Capture energy from braking and return to the grid",
             "pct": 0.20, "installed": _all_records_flagged(lifts, "lift_regenerative_features")},
            {"key": "lift_vvvf", "label": "VVVF drive & sleep mode",
             "description": "Variable-voltage variable-frequency drive with sleep mode",
             "pct": 0.40, "installed": _all_records_flagged(lifts, "vvvf_sleep_mode")},
        ]
    return []


def _refrigerant_scope1_saving(building, floor_area):
    """Scope-1 refrigerant-transition saving (kgCO2eq/m²/yr), summed over cooling units.

    For each AC + chiller: qty_kg * (leakage%/100) * (baseline_GWP - natural_GWP) / GFA.
    Target = lowest-GWP natural refrigerant available. Units already at/below the
    target GWP, or with missing refrigerant data, contribute zero.
    """
    from pages.models.building_operation.chilling import RefrigerantGWP

    if not floor_area or Decimal(str(floor_area)) <= 0:
        return 0.0, None
    gfa = Decimal(str(floor_area))

    # Cheapest available natural target.
    target_gwp = None
    for code in _NATURAL_REFRIGERANTS:
        gwp = RefrigerantGWP.get_gwp(code)
        if gwp is not None:
            target_gwp = Decimal(str(gwp))
            break
    if target_gwp is None:
        return 0.0, None

    units = list(building.chillers.all()) + list(building.air_conditioners.all())

    total = Decimal("0")
    for u in units:
        qty = getattr(u, "refrigerant_quantity_kg", None)
        gwp = getattr(u, "baseline_refrigerant_emission_factor", None)
        leakage = getattr(u, "baseline_leakage_factor_percent", None)
        if qty is None or gwp is None or leakage is None:
            continue
        gwp = Decimal(str(gwp))
        if gwp <= target_gwp:
            continue
        saving = Decimal(str(qty)) * (Decimal(str(leakage)) / Decimal("100")) \
            * (gwp - target_gwp) / gfa
        total += saving

    return round(float(total), 2), (float(target_gwp) if total > 0 else None)


def get_operational_savings_measures(
    building: Building,
    prefetched_operational=None,
) -> Dict[str, Any]:
    """Layer 3 — per-system optimisation measures, BMS and refrigerant transition.

    Reuses get_operational_carbon_by_system() for the per-system baseline carbon
    (kgCO2eq/m²/yr) so the numbers match the Systems tab exactly. Per-system
    measures stack multiplicatively; BMS applies last to the whole-building
    electricity total; refrigerant Scope-1 is additive and separate. Returns a
    dict shaped for savings_tab.html and safe for JSON serialisation.
    """
    by_system = get_operational_carbon_by_system(
        building, prefetched_operational=prefetched_operational
    )
    baseline_labels = by_system.get("labels", [])
    baseline_absolute = by_system.get("absolute", [])
    electricity_total = float(by_system.get("total", 0.0) or 0.0)

    systems = []
    optimized_electricity = 0.0
    for label, baseline in zip(baseline_labels, baseline_absolute):
        style = _SYSTEM_STYLE.get(label)
        if not style:
            continue
        baseline = float(baseline)
        measures = _measures_for_system(style["key"], building)

        # Stack available (not-installed) measures multiplicatively.
        remaining = baseline
        measure_rows = []
        for m in measures:
            applies = not m["installed"]
            saving = remaining * m["pct"] if applies else 0.0
            if applies:
                remaining -= saving
            measure_rows.append({
                "key": m["key"],
                "label": m["label"],
                "description": m["description"],
                "pct": m["pct"],
                "installed": m["installed"],
                "saving": round(saving, 2),
            })
        optimized = round(remaining, 2)
        optimized_electricity += optimized
        reduction_pct = round((baseline - optimized) / baseline * 100, 1) if baseline > 0 else 0.0
        share_pct = round(baseline / electricity_total * 100, 1) if electricity_total > 0 else 0.0

        systems.append({
            "label": label,
            "key": style["key"],
            "icon": style["icon"],
            "color": style["color"],
            "baseline": round(baseline, 2),
            "optimized": optimized,
            "reduction_pct": reduction_pct,
            "share_pct": share_pct,
            "measures": measure_rows,
        })

    # BMS applies last, multiplicatively, to the whole-building electricity total.
    bms_saving = round(optimized_electricity * 0.20, 2)
    optimized_after_bms = round(optimized_electricity - bms_saving, 2)

    # Refrigerant (Scope 1) — additive, separate from electricity.
    refrigerant_saving, target_gwp = _refrigerant_scope1_saving(
        building, building.total_floor_area
    )

    baseline_total = round(electricity_total, 2)
    optimized_total = round(optimized_after_bms - refrigerant_saving, 2)
    total_saving = round(baseline_total - optimized_total, 2)
    reduction_pct = round(total_saving / baseline_total * 100, 1) if baseline_total > 0 else 0.0

    period = building.reference_period or 50

    return {
        "systems": systems,
        "bms": {
            "label": "Building Management System (BMS)",
            "description": "Whole-building controls optimisation",
            "pct": 0.20,
            "saving": bms_saving,
        },
        "refrigerant": {
            "label": "Refrigerant transition (natural refrigerant)",
            "saving": refrigerant_saving,
            "target_gwp": target_gwp,
            "has_saving": refrigerant_saving > 0,
        },
        "baseline_total": baseline_total,
        "optimized_total": optimized_total,
        "total_saving": total_saving,
        "reduction_pct": reduction_pct,
        "baseline_total_lifetime": round(baseline_total * period),
        "optimized_total_lifetime": round(optimized_total * period),
        "total_saving_lifetime": round(total_saving * period),
        "reference_period": period,
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

    # Layer 1 — operational EUI benchmark position (actual EUI vs national/best practice)
    operational_benchmark = get_operational_benchmark_for_building(building)
    operational_benchmark_position = None
    if operational_benchmark:
        summary = getattr(building, 'energy_summary', None)
        floor_area = building.total_floor_area
        actual_eui = None
        if summary is not None and floor_area and Decimal(str(floor_area)) > 0:
            total_kwh = summary.total_kwh
            if total_kwh:
                actual_eui = float(Decimal(str(total_kwh)) / Decimal(str(floor_area)))
        grid_factor = _derive_grid_emission_factor(building, prefetched_operational)
        # Fall back to the country's reference grid EF when no electricity EPD gave one.
        if not grid_factor or float(grid_factor) <= 0:
            from pages.views.building.operational_benchmark_data import GRID_EF_FALLBACK
            grid_factor = GRID_EF_FALLBACK.get(operational_benchmark["country"], 0)
        operational_benchmark_position = calculate_operational_benchmark_position(
            actual_eui, operational_benchmark, grid_factor,
            floor_area, building.reference_period,
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
        'operational_benchmark': operational_benchmark,
        'operational_benchmark_position': operational_benchmark_position,
        'operational_savings': get_operational_savings_measures(
            building, prefetched_operational=prefetched_operational
        ),
    }