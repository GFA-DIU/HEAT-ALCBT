import logging

from django.contrib.auth.decorators import login_required
from django.core import serializers
from django.db import models, transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_http_methods

from accounts.forms import CustomUserUpdateForm, UserProfileUpdateForm
from pages.models.assembly import Assembly, AssemblyMode, StructuralProduct
from pages.models.building import (Building, BuildingAssembly,
                                   BuildingAssemblySimulated, OperationalProduct)
from pages.models.epd import EPDImpact
from pages.views.building.building_stats import (
    calculate_total_embodied_carbon, calculate_total_operational_carbon)

logger = logging.getLogger(__name__)


def _buildings_with_stats(buildings):
    """Attach card stats to each building, prefetching assemblies/products/impacts
    and operational products so embodied + operational carbon are computed without
    an N+1 explosion. Only the values the card shows are computed (footprint,
    embodied, progress) — the unused carbon-savings baseline is skipped."""
    buildings = buildings.select_related(
        "country", "category__category", "energy_summary"
    ).prefetch_related(
        # System relations so the progress bar's checks hit the prefetch cache
        # instead of ~8 count/exists queries per building.
        "air_conditioners", "chillers", "ventilation_systems",
        "lighting_systems", "lift_escalator_systems", "hot_water_systems",
        models.Prefetch(
            "buildingassembly_set",
            queryset=BuildingAssembly.objects.select_related("assembly").prefetch_related(
                models.Prefetch(
                    "assembly__structuralproduct_set",
                    queryset=StructuralProduct.objects.select_related("epd", "classification").prefetch_related(
                        models.Prefetch(
                            "epd__epdimpact_set",
                            queryset=EPDImpact.objects.select_related("impact"),
                            to_attr="all_impacts",
                        ),
                    ),
                    to_attr="prefetched_products",
                ),
            ),
            to_attr="prefetched_components",
        ),
        models.Prefetch(
            "operational_products",
            queryset=OperationalProduct.objects.select_related("epd").prefetch_related(
                models.Prefetch(
                    "epd__epdimpact_set",
                    queryset=EPDImpact.objects.select_related("impact"),
                    to_attr="all_impacts",
                ),
            ),
            to_attr="prefetched_ops",
        ),
    )
    result = []
    for b in buildings:
        embodied = calculate_total_embodied_carbon(b, prefetched_assemblies=b.prefetched_components)
        operational = calculate_total_operational_carbon(b, prefetched_operational=b.prefetched_ops)
        b.stats = {
            "total_embodied_carbon": embodied,
            "total_carbon_footprint": embodied + operational,
            "progress_percentage": _progress_from_prefetch(b),
        }
        result.append(b)
    return result


def _progress_from_prefetch(b):
    """Same weighting as calculate_progress_percentage, but reads the prefetched
    relations (no per-building count/exists queries)."""
    p = 0
    if b.name and b.address and b.country_id:
        p += 10
    if b.category_id and b.total_floor_area:
        p += 10
    if len(b.prefetched_ops) > 0:
        p += 30
    if len(b.prefetched_components) > 0:
        p += 40
    if len(b.air_conditioners.all()) or len(b.chillers.all()) or b.cooling_not_applicable:
        p += 2
    if len(b.ventilation_systems.all()) or b.ventilation_not_applicable:
        p += 2
    if len(b.lighting_systems.all()) or b.lighting_not_applicable:
        p += 2
    if len(b.lift_escalator_systems.all()) or b.lift_not_applicable:
        p += 2
    if len(b.hot_water_systems.all()) or b.hot_water_not_applicable:
        p += 2
    return min(p, 100)


SORT_OPTIONS = {
    "name_asc": "name",
    "name_desc": "-name",
    "date_desc": "-created_at",
    "date_asc": "created_at",
}
DEFAULT_SORT = "date_desc"


@login_required
@require_http_methods(["GET", "POST", "DELETE"])
def buildings_list(request):
    buildings = Building.objects.filter(created_by=request.user).exclude(is_example=True)

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

    # Handle sorting
    sort_query = request.GET.get("sort", DEFAULT_SORT)
    if sort_query not in SORT_OPTIONS:
        sort_query = DEFAULT_SORT
    buildings = buildings.order_by(SORT_OPTIONS[sort_query])

    # Check if this is a new user (first time on home page after signup)
    show_account_success_modal = request.session.pop('show_account_success_modal', False)

    # Initialize forms for the account success modal
    user_form = CustomUserUpdateForm(instance=request.user)
    profile_form = UserProfileUpdateForm(instance=request.user.userprofile)

    # Calculate statistics for each building (prefetched, N+1-free)
    buildings_with_stats = _buildings_with_stats(buildings)

    context = {
        "buildings": buildings_with_stats,
        "search_query": search_query,
        "sort_query": sort_query,
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
    sort_query = request.GET.get("sort", DEFAULT_SORT)
    if sort_query not in SORT_OPTIONS:
        sort_query = DEFAULT_SORT
    buildings = (
        Building.objects.filter(created_by=request.user)
        .exclude(is_example=True)
        .order_by(SORT_OPTIONS[sort_query])
    )
    buildings_with_stats = _buildings_with_stats(buildings)

    context = {"buildings": buildings_with_stats, "sort_query": sort_query}
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

    # Delete certification file and BoQ files from storage before deleting the building
    if building_to_delete.certification_file:
        building_to_delete.certification_file.delete(save=False)
    for boq in building_to_delete.boq_files.all():
        boq.file.delete(save=False)

    building_to_delete.delete()
    logger.info("Successfully deleted building '%s' from list", building_to_delete)