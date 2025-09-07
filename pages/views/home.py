import logging

from django.db import transaction
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required

from pages.models.assembly import Assembly, AssemblyMode
from pages.models.building import Building, BuildingAssembly, BuildingAssemblySimulated


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