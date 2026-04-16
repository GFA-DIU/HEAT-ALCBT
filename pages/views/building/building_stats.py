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
from typing import Dict, Any, List
from django.db.models import Sum, Q

from pages.models.building import Building
from pages.models.building_operation.chilling import CoolingSystemChiller
from pages.models.building_operation.air_conditioning import CoolingSystemAirConditioner
from pages.views.building.impact_calculation import calculate_impacts, calculate_impact_operational

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
    has_cooling = (
        CoolingSystemChiller.objects.filter(building=building).exists() or
        CoolingSystemAirConditioner.objects.filter(building=building).exists()
    )
    if has_cooling:
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


def calculate_total_embodied_carbon(building: Building, simulated: bool = False) -> Decimal:
    """
    Calculate total embodied carbon (GWP A1-A3) from structural components.

    Args:
        building: Building instance to calculate for
        simulated: If True, calculate for simulated components; if False, for actual components

    Returns:
        Total embodied carbon in kgCO2e/m² (normalized by floor area)
    """
    total_gwp = Decimal('0.0')

    if simulated:
        # Get simulated assemblies
        building_assemblies = building.buildingassemblysimulated_set.all()
    else:
        # Get actual assemblies
        building_assemblies = building.buildingassembly_set.all()

    for ba in building_assemblies:
        assembly = ba.assembly
        assembly_quantity = ba.quantity

        # Get all structural products in this assembly
        for structural_product in assembly.structuralproduct_set.all():
            try:
                # Calculate impacts for this product
                impacts = calculate_impacts(
                    dimension=assembly.dimension,
                    assembly_quantity=assembly_quantity,
                    total_floor_area=float(building.total_floor_area),
                    p=structural_product
                )

                # Sum up GWP impacts (A1-A3)
                for impact in impacts:
                    if impact['impact_type'].impact_category == 'gwp' and \
                       impact['impact_type'].life_cycle_stage in ['a1a3', 'a1-a3']:
                        total_gwp += Decimal(str(impact['impact_value']))

            except (ValueError, AttributeError, ZeroDivisionError) as e:
                # Skip products with calculation errors
                continue

    return total_gwp


def calculate_total_operational_carbon(building: Building, simulated: bool = False) -> Decimal:
    """
    Calculate total operational carbon (GWP B6) from operational products.

    Args:
        building: Building instance to calculate for
        simulated: If True, calculate for simulated products; if False, for actual products

    Returns:
        Total operational carbon in kgCO2e/m² (normalized by floor area)
    """
    total_gwp_b6 = Decimal('0.0')

    if simulated:
        operational_products = building.simulated_operational_products.all()
    else:
        operational_products = building.operational_products.all()

    reference_period = Decimal(str(building.reference_period))

    for op in operational_products:
        try:
            impacts = calculate_impact_operational(op)
            total_gwp_b6 += impacts.get('gwp_b6', Decimal('0.0')) * reference_period
        except (ValueError, AttributeError, ZeroDivisionError) as e:
            # Skip products with calculation errors
            continue

    return total_gwp_b6


def calculate_total_carbon_footprint(building: Building, simulated: bool = False) -> Decimal:
    """
    Calculate total carbon footprint (embodied + operational).

    Args:
        building: Building instance to calculate for
        simulated: If True, calculate for simulated components; if False, for actual components

    Returns:
        Total carbon footprint in kgCO2e/m²
    """
    embodied = calculate_total_embodied_carbon(building, simulated=simulated)
    operational = calculate_total_operational_carbon(building, simulated=simulated)

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

def get_building_detail_statistics(building: Building) -> Dict[str, Any]:
    """
    Get all statistics for a building detail page.

    This includes all the statistics from get_building_statistics plus
    operational carbon which is displayed on the detail page.

    Args:
        building: Building instance to calculate statistics for

    Returns:
        Dictionary containing all building statistics for detail page:
        - total_carbon_footprint: Decimal (kgCO2e/m²)
        - total_embodied_carbon: Decimal (kgCO2e/m²)
        - total_operational_carbon: Decimal (kgCO2e/m²)
        - carbon_savings_percentage: Decimal (%)
    """
    embodied = calculate_total_embodied_carbon(building, simulated=False)
    operational = calculate_total_operational_carbon(building, simulated=False)

    return {
        'total_carbon_footprint': embodied + operational,
        'total_embodied_carbon': embodied,
        'total_operational_carbon': operational,
        'carbon_savings_percentage': calculate_carbon_savings_percentage(building),
    }


def get_embodied_carbon_by_assembly(building: Building, simulated: bool = False) -> Dict[str, Any]:
    """
    Calculate embodied carbon grouped by assembly classification.

    Args:
        building: Building instance to calculate for
        simulated: If True, calculate for simulated components

    Returns:
        Dictionary with 'labels' and 'data' for chart rendering
    """
    carbon_by_assembly = defaultdict(Decimal)

    if simulated:
        building_assemblies = building.buildingassemblysimulated_set.all()
    else:
        building_assemblies = building.buildingassembly_set.all()

    for ba in building_assemblies:
        assembly = ba.assembly
        assembly_quantity = ba.quantity
        assembly_name = assembly.name or "Unknown"

        for structural_product in assembly.structuralproduct_set.all():
            try:
                impacts = calculate_impacts(
                    dimension=assembly.dimension,
                    assembly_quantity=assembly_quantity,
                    total_floor_area=float(building.total_floor_area),
                    p=structural_product
                )

                for impact in impacts:
                    if impact['impact_type'].impact_category == 'gwp' and \
                       impact['impact_type'].life_cycle_stage in ['a1a3', 'a1-a3']:
                        # Use per-product classification (same source as old dashboard)
                        assembly_category = impact.get('assembly_category', '')
                        if assembly_category:
                            full_label = str(assembly_category)
                            label = full_label.split("- ", 1)[1] if "- " in full_label else full_label
                        else:
                            label = assembly_name
                        carbon_by_assembly[label] += Decimal(str(impact['impact_value']))

            except (ValueError, AttributeError, ZeroDivisionError):
                continue

    # Sort by value descending and take top items
    sorted_items = sorted(carbon_by_assembly.items(), key=lambda x: x[1], reverse=True)

    # Calculate total for percentage
    total = sum(v for _, v in sorted_items) or Decimal('1')

    labels = []
    data = []
    absolute = []
    for label, value in sorted_items[:10]:  # Top 10 items
        labels.append(label)
        percentage = float((value / total) * 100)
        data.append(round(percentage, 1))
        absolute.append(round(float(value), 2))

    return {'labels': labels, 'data': data, 'absolute': absolute}


def get_embodied_carbon_by_material(building: Building, simulated: bool = False) -> Dict[str, Any]:
    """
    Calculate embodied carbon grouped by material category.

    Args:
        building: Building instance to calculate for
        simulated: If True, calculate for simulated components

    Returns:
        Dictionary with 'labels' and 'data' for chart rendering
    """
    carbon_by_material = defaultdict(Decimal)

    if simulated:
        building_assemblies = building.buildingassemblysimulated_set.all()
    else:
        building_assemblies = building.buildingassembly_set.all()

    for ba in building_assemblies:
        assembly = ba.assembly
        assembly_quantity = ba.quantity

        for structural_product in assembly.structuralproduct_set.all():
            try:
                # Map EPD category name using the same mapping as the old dashboard
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
                       impact['impact_type'].life_cycle_stage in ['a1a3', 'a1-a3']:
                        carbon_by_material[material_category] += Decimal(str(impact['impact_value']))

            except (ValueError, AttributeError, ZeroDivisionError):
                continue

    # Sort by value descending
    sorted_items = sorted(carbon_by_material.items(), key=lambda x: x[1], reverse=True)

    # Calculate total for percentage
    total = sum(v for _, v in sorted_items) or Decimal('1')

    labels = []
    data = []
    absolute = []
    for label, value in sorted_items[:10]:  # Top 10 items
        labels.append(label)
        percentage = float((value / total) * 100)
        data.append(round(percentage, 1))
        absolute.append(round(float(value), 2))

    return {'labels': labels, 'data': data, 'absolute': absolute}


def get_operational_carbon_by_system(building: Building, simulated: bool = False) -> Dict[str, Any]:
    """
    Calculate operational carbon grouped by system type (cooling, ventilation, etc.).

    Args:
        building: Building instance to calculate for
        simulated: If True, calculate for simulated components

    Returns:
        Dictionary with 'labels' and 'data' for chart rendering
    """
    carbon_by_system = defaultdict(Decimal)

    if simulated:
        operational_products = building.simulated_operational_products.all()
    else:
        operational_products = building.operational_products.all()

    reference_period = Decimal(str(building.reference_period))

    for op in operational_products:
        try:
            # Categorize by EPD category or use a default
            system_type = "Other Systems"
            if op.epd and op.epd.category:
                category_name = op.epd.category.name_en.lower() if op.epd.category.name_en else ""

                if 'cool' in category_name or 'refriger' in category_name:
                    system_type = "Cooling systems"
                elif 'ventil' in category_name or 'air' in category_name:
                    system_type = "Ventilation systems"
                elif 'light' in category_name or 'lamp' in category_name:
                    system_type = "Lighting systems"
                elif 'lift' in category_name or 'elevator' in category_name or 'escalator' in category_name:
                    system_type = "Lift & escalator"
                elif 'water' in category_name or 'heat' in category_name:
                    system_type = "Hot Water Systems"
                elif 'electr' in category_name or 'energy' in category_name or 'power' in category_name:
                    system_type = "Electricity"
                elif 'gas' in category_name or 'fuel' in category_name:
                    system_type = "Gas/Fuel"

            impacts = calculate_impact_operational(op)
            gwp_b6 = impacts.get('gwp_b6', Decimal('0.0')) * reference_period
            carbon_by_system[system_type] += gwp_b6

        except (ValueError, AttributeError, ZeroDivisionError):
            continue

    # Sort by value descending
    sorted_items = sorted(carbon_by_system.items(), key=lambda x: x[1], reverse=True)

    # Calculate total for percentage
    total = sum(v for _, v in sorted_items) or Decimal('1')

    labels = []
    data = []
    absolute = []
    for label, value in sorted_items:
        labels.append(label)
        percentage = float((value / total) * 100)
        data.append(round(percentage, 1))
        absolute.append(round(float(value), 2))

    return {'labels': labels, 'data': data, 'absolute': absolute}


def get_building_chart_data(building: Building) -> Dict[str, Any]:
    """
    Get all chart data for a building detail page.

    Args:
        building: Building instance to get chart data for

    Returns:
        Dictionary containing chart data for:
        - whole_life_carbon: data for doughnut chart (embodied vs operational)
        - embodied_by_assembly: data for bar chart by assembly
        - embodied_by_material: data for bar chart by material
        - operational_by_system: data for bar chart by system/appliance
    """
    embodied = calculate_total_embodied_carbon(building, simulated=False)
    operational = calculate_total_operational_carbon(building, simulated=False)

    return {
        'whole_life_carbon': {
            'labels': ['Operational carbon', 'Embodied carbon'],
            'data': [float(operational), float(embodied)],
        },
        'embodied_by_assembly': get_embodied_carbon_by_assembly(building),
        'embodied_by_material': get_embodied_carbon_by_material(building),
        'operational_by_system': get_operational_carbon_by_system(building),
    }