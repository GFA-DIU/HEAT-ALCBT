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
    assemblies_to_delete = Assembly.objects.filter(
            id__in=assemblies_list,
            mode=AssemblyMode.CUSTOM
        )
    logger.info("Delete %s out of %s assemblies from building %s", len(assemblies_list), len(assemblies_to_delete), building_id)
    assemblies_to_delete.delete()
    
    
    building_to_delete = get_object_or_404(Building, id=building_id)
    building_to_delete.delete()
    logger.info("Successfully deleted building '%s' from list", building_to_delete)


def get_material_category_mapping():
    # Load material category mapping from JSON file
    mapping_file = Path(__file__).parent / 'building' / 'building_dashboard' / 'material_category_mapping.json'
    with open(mapping_file, 'r') as f:
        return json.load(f)


def get_category_short_name(category_name, is_structural):
    short_name = category_name

    if is_structural and "- " in category_name:
        short_name = category_name.split("- ")[1]

    if short_name == "Intermediate Floor Construction":
        return "Interm. Floor"
    elif short_name == "Bottom Floor Construction":
        return "Bottom Floor"
    elif short_name == "Roof Construction":
        return "Roof Const."

    return short_name


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
    total_gwp = df['gwp'].sum()
    operational_gwp = df[df['type'] == 'operational']['gwp'].sum()
    embodied_gwp = df[df['type'] == 'structural']['gwp'].sum()

    total_penrt = df['penrt'].sum()
    operational_penrt = df[df['type'] == 'operational']['penrt'].sum()
    embodied_penrt = df[df['type'] == 'structural']['penrt'].sum()


    csv_data = []

    # Add summary totals
    csv_data.append(['Total', 'All', total_gwp, total_penrt, 'total'])
    csv_data.append(['Operational Total', 'All', operational_gwp, operational_penrt, 'operational_total'])
    csv_data.append(['Embodied Total', 'All', embodied_gwp, embodied_penrt, 'embodied_total'])

    # Add embodied emissions by category (shortened names from dashboard)
    if len(df[df['type'] == 'structural']) > 0:
        embodied_by_category = df[df['type'] == 'structural'].groupby('assembly_category').agg({
            'gwp': 'sum',
            'penrt': 'sum'
        }).reset_index()

        for _, row in embodied_by_category.iterrows():
            category_short = get_category_short_name(row['assembly_category'], True)
            csv_data.append([
                f'Embodied - {category_short}',
                'Category',
                row['gwp'],
                row['penrt'],
                'embodied_by_category'
            ])

    # Add embodied emissions by material (using mapping from JSON)
    if len(df[df['type'] == 'structural']) > 0:
        embodied_by_material = df[df['type'] == 'structural'].groupby('material_category').agg({
            'gwp': 'sum',
            'penrt': 'sum'
        }).reset_index()

        for _, row in embodied_by_material.iterrows():
            material_name = row['material_category']
            mapped_category = material_mapping.get(material_name, 'Others')
            csv_data.append([
                f'Embodied - {mapped_category}',
                material_name,
                row['gwp'],
                row['penrt'],
                'embodied_by_material'
            ])

    # Add operational emissions by category if any
    if len(df[df['type'] == 'operational']) > 0:
        operational_by_category = df[df['type'] == 'operational'].groupby('material_category').agg({
            'gwp': 'sum',
            'penrt': 'sum'
        }).reset_index()

        for _, row in operational_by_category.iterrows():
            csv_data.append([
                f'Operational - {row["material_category"]}',
                row['material_category'],
                row['gwp'],
                row['penrt'],
                'operational_by_category'
            ])

    # Create CSV response
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="{building.name}_emissions_export.csv"'

    writer = csv.writer(response, delimiter=';')
    writer.writerow(['Category', 'Material_Category', 'GWP_kg_CO2eq_m2', 'PENRT_MJ_m2', 'Type'])

    for row in csv_data:
        writer.writerow(row)

    logger.info(f"Building {building_id} CSV export completed for user {request.user}")
    return response