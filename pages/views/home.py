import logging

from django.contrib.auth.decorators import login_required
from django.core import serializers
from django.db import models, transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_http_methods

from accounts.forms import CustomUserUpdateForm, UserProfileUpdateForm
from pages.models.assembly import Assembly, AssemblyMode
from pages.models.building import (Building, BuildingAssembly,
                                   BuildingAssemblySimulated)
from pages.views.building.building_stats import get_building_statistics

logger = logging.getLogger(__name__)


@login_required
@require_http_methods(["GET", "POST", "DELETE"])
def buildings_list(request):
    buildings = Building.objects.filter(created_by=request.user)

    # Handle search query
    search_query = request.GET.get("search", "").strip()
    if search_query:
        logger.info("Searching buildings with query: '%s'", search_query)
        buildings = buildings.filter(
            models.Q(name__icontains=search_query) |
            models.Q(city__name__icontains=search_query) |
            models.Q(country__name__icontains=search_query) |
            models.Q(category__category__name__icontains=search_query) |
            models.Q(category__subcategory__name__icontains=search_query) |
            models.Q(street__icontains=search_query)
        ).distinct()

    # Check if this is a new user (first time on home page after signup)
    show_account_success_modal = request.session.pop('show_account_success_modal', False)

    # Initialize forms for the account success modal
    user_form = CustomUserUpdateForm(instance=request.user)
    profile_form = UserProfileUpdateForm(instance=request.user.userprofile)

    # Calculate statistics for each building
    buildings_with_stats = []
    for building in buildings:
        stats = get_building_statistics(building)
        # Attach statistics as attributes to the building object
        building.stats = stats
        buildings_with_stats.append(building)

    context = {
        "buildings": buildings_with_stats,
        "search_query": search_query,
        "show_account_success_modal": show_account_success_modal,
        "user_form": user_form,
        "profile_form": profile_form,
    }

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
        if request.headers.get("HX-Request"):
            return render(request, "pages/home/partials/buildings_list.html", context)
        return JsonResponse({"status": "success"}, status=200)
    
    # If HTMX request, return only the buildings list partial
    if request.headers.get("HX-Request"):
        return render(request, "pages/home/partials/buildings_list.html", context)

    # Full page load for GET request
    logger.info("Serving full item list page for GET request")
    # return JsonResponse(serializers.serialize('json', buildings), safe=False)
    return render(request, "pages/home/home.html", context)


@transaction.atomic
def handle_delete_building(request):
    building_id = request.GET.get("building_id")

    try:
        _delete_building(building_id)

    except:
        logger.exception("Error occured when trying to delete building: %s", building_id)


    # Get remaining buildings and add statistics
    buildings = Building.objects.filter(created_by=request.user)
    buildings_with_stats = []
    for building in buildings:
        stats = get_building_statistics(building)
        building.stats = stats
        buildings_with_stats.append(building)

    context = {"buildings": buildings_with_stats}
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