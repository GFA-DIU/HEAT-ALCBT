import csv
import json
import logging
from pathlib import Path

from django.db import transaction
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required

from pages.models.assembly import Assembly, AssemblyMode
from pages.models.building import Building, BuildingAssembly, BuildingAssemblySimulated
from pages.views.building.building_dashboard.utility import prep_building_dashboard_df


logger = logging.getLogger(__name__)


@login_required
@require_http_methods(["GET", "POST", "DELETE"])
def buildings_list(request):
    buildings = Building.objects.filter(created_by=request.user)
    context = {"buildings": buildings}

    logger.info("User: %s access list view.", request.user)

    if request.method == "POST":
        new_item = request.POST.get("item")
        if new_item and len(buildings) < 5:
            logger.info("Add item: '%s' to list", new_item)
            buildings.append(new_item)
        return render(
            request, "pages/home/building_list/item.html", context
        )  # Partial update for POST

    elif request.method == "DELETE":
        context = handle_delete_building(request)
        return render(request, "pages/home/buildings_list.html", context)

    # Handle CSV export request
    if request.method == "GET" and request.GET.get("export") == "csv":
        building_id = request.GET.get("building_id")
        if building_id:
            return handle_building_export(request, building_id)

    # Full page load for GET request
    logger.info("Serving full item list page for GET request")
    return render(request, "pages/home/home.html", context)


@transaction.atomic
def handle_delete_building(request):
    building_id = request.GET.get("building_id")
    
    try:
        _delete_building(building_id)
    
    except:
        logger.exception("Error occured when trying to delete building: %s", building_id)
        
        

    context = {"buildings": Building.objects.filter(created_by=request.user)}
    return context


def _delete_building(building_id):
    # Delete assemblies
    # TODO: Change once assemblies are managed separately
    assemblies_list = (
        BuildingAssembly.objects.filter(building__id=building_id).values_list('assembly_id', flat=True).union(
            BuildingAssemblySimulated.objects.filter(building__id=building_id).values_list('assembly_id', flat=True)
        )
    )

    # Find and delete associated assemblies with AssemblyMode.CUSTOM
    # But preserve assemblies that are templates (should not be deleted when building is deleted)
    assemblies_to_delete = Assembly.objects.filter(
            id__in=assemblies_list,
            mode=AssemblyMode.CUSTOM,
            is_template=False  # Only delete non-template assemblies
        )
    logger.info("Delete %s out of %s assemblies from building %s (templates preserved)", len(assemblies_to_delete), len(assemblies_list), building_id)
    assemblies_to_delete.delete()
    
    
    building_to_delete = get_object_or_404(Building, id=building_id)
    building_to_delete.delete()
    logger.info("Successfully deleted building '%s' from list", building_to_delete)


def get_material_category_mapping():
    # Load material category mapping from JSON file
    mapping_file = Path(__file__).parent / 'building' / 'building_dashboard' / 'material_category_mapping.json'
    with open(mapping_file, 'r') as f:
        return json.load(f)


def get_category_short_name(category_name: str, is_structural: bool) -> str:

    # Strip structural prefix if present
    short_name = category_name.split("- ", 1)[-1] if is_structural and "- " in category_name else category_name

    # Mapping of full names to short names
    category_map = {
        "Intermediate Floor Construction": "Interm. Floor",
        "Bottom Floor Construction": "Bottom Floor",
        "Roof Construction": "Roof Const.",
    }

    return category_map.get(short_name, short_name)


def aggregate_and_append(df, group_field, label_prefix, type_label, material_mapping=None, transform_label=None):

    # Aggregate emissions data by a given field and return formatted CSV rows.

    csv_rows = []
    grouped = df.groupby(group_field).agg({"gwp": "sum", "penrt": "sum"}).reset_index()

    for _, row in grouped.iterrows():
        label = row[group_field]

        # Apply transformations if provided
        if transform_label:
            label = transform_label(label)
        if material_mapping:
            label = material_mapping.get(row[group_field], "Others")

        csv_rows.append([
            f"{label_prefix} - {label}" if label_prefix else label,
            row[group_field] if not material_mapping else row[group_field],
            row["gwp"],
            row["penrt"],
            type_label
        ])
    return csv_rows


def handle_building_export(request, building_id):
    # Verify user owns this building
    building = get_object_or_404(Building, pk=building_id, created_by=request.user)

    # Get the same data used in dashboard
    simulation = request.GET.get('simulation', 'false').lower() == 'true'
    df = prep_building_dashboard_df(request.user, building_id, simulation)

    if df is None or len(df) == 0:
        # Return empty CSV with headers if no data
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="{building.name}_emissions_export.csv"'
        writer = csv.writer(response, delimiter=';')
        writer.writerow(['Category', 'Material_Category', 'GWP_kg_CO2eq_m2', 'PENRT_MJ_m2', 'Type'])
        return response

    # Load material category mapping
    material_mapping = get_material_category_mapping()

    # Calculate aggregated totals
    csv_data = [
        ['Total', 'All', df['gwp'].sum(), df['penrt'].sum(), 'total'],
        ['Operational Total', 'All', df[df['type'] == 'operational']['gwp'].sum(),
         df[df['type'] == 'operational']['penrt'].sum(), 'operational_total'],
        ['Embodied Total', 'All', df[df['type'] == 'structural']['gwp'].sum(),
         df[df['type'] == 'structural']['penrt'].sum(), 'embodied_total']
    ]

    # Add embodied emissions by category and material
    structural_df = df[df['type'] == 'structural']
    if len(structural_df) > 0:
        csv_data.extend(aggregate_and_append(
            structural_df, 'assembly_category', 'Embodied', 'embodied_by_category',
            transform_label=lambda label: get_category_short_name(label, True)
        ))
        csv_data.extend(aggregate_and_append(
            structural_df, 'material_category', 'Embodied', 'embodied_by_material',
            material_mapping=material_mapping
        ))

    # Add operational emissions by category
    operational_df = df[df['type'] == 'operational']
    if len(operational_df) > 0:
        csv_data.extend(aggregate_and_append(
            operational_df, 'material_category', 'Operational', 'operational_by_category'
        ))

    # Create CSV response
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="{building.name}_emissions_export.csv"'

    writer = csv.writer(response, delimiter=';')
    writer.writerow(['Category', 'Material_Category', 'GWP_kg_CO2eq_m2', 'PENRT_MJ_m2', 'Type'])
    writer.writerows(csv_data)

    logger.info(f"Building {building_id} CSV export completed for user {request.user}")
    return response