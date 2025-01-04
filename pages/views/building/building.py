import logging

from django.db.models import Prefetch
from django.http import HttpResponseServerError
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_http_methods

from pages.forms.building_general_info import BuildingGeneralInformation
from pages.models.assembly import DIMENSION_UNIT_MAPPING
from pages.models.building import Building, BuildingAssembly, BuildingAssemblySimulated

from pages.scripts.dashboards.building_dashboard import building_dashboard
from pages.scripts.dashboards.impact_calculation import calculate_impacts


logger = logging.getLogger(__name__)


@require_http_methods(["GET", "POST", "DELETE"])
def building(request, building_id=None):
    logger.info("Building - Request method: %s, user: %s", request.method, request.user)

    # General Info
    if request.method == "POST" and request.POST.get("action") == "general_information":
        return handle_general_information_submit(request, building_id)

    elif request.method == "DELETE":
        return handle_assembly_delete(request, building_id)

    # Full reload
    elif building_id:
        context, form = handle_building_load(request, building_id, simulation=False)

    else:
        # Blank for new building
        context = {
            "building_id": None,
            "building": None,
            "structural_components": [],
        }
        form = BuildingGeneralInformation()

    context["form_general_info"] = form
    context["simulation"] = False
    # Full page load for GET request
    logger.info("Serving full item list page for GET request")
    return render(request, "pages/building/building.html", context)


def handle_building_load(request, building_id, simulation):
    if simulation:
        BuildingAssemblyModel = BuildingAssemblySimulated
    else:
        BuildingAssemblyModel = BuildingAssembly
    
    building = get_object_or_404(
        Building.objects.filter(
            created_by=request.user
        ).prefetch_related(  # Ensure the building belongs to the user
            Prefetch(
                "buildingassembly_set",
                queryset=BuildingAssemblyModel.objects.filter(
                    # assembly__created_by=request.user  # Ensure the assembly belongs to the user
                ).select_related("assembly"),
                to_attr="prefetched_components",
            )
        ),
        pk=building_id,
    )

    # Build structural components and impacts in one step
    structural_components, impact_list = get_assemblies(building.prefetched_components)

    context = {
        "building_id": building.id,
        "building": building,
        "structural_components": structural_components,
    }
    if len(structural_components):
        context["dashboard"] = building_dashboard(impact_list)

    form = BuildingGeneralInformation(instance=building)

    logger.info(
        "Found building: %s with %d structural components",
        building.name,
        len(context["structural_components"]),
    )

    return context, form


def handle_general_information_submit(request, building_id):
    building = (
        get_object_or_404(Building, created_by=request.user, pk=building_id)
        if building_id
        else None
    )
    form = BuildingGeneralInformation(
        request.POST, instance=building
    )  # Bind form to instance
    if form.is_valid():
        building = form.save(commit=False)
        building.created_by = request.user
        building.save()
        return redirect("building", building_id=building.id)
    else:
        return HttpResponseServerError()


def handle_assembly_delete(request, building_id):
    component_id = request.GET.get("component")
    # Get the component and delete it
    component = get_object_or_404(
        BuildingAssembly, id=component_id, building__id=building_id
    )
    component.delete()

    # Fetch the updated list of assemblies for the building
    updated_list = BuildingAssembly.objects.filter(
        building__created_by=request.user,
        assembly__created_by=request.user,
        building_id=building_id,
    ).select_related(
        "assembly"
    )  # Optimize query by preloading related Assembly
    structural_components, _ = get_assemblies(updated_list)
    context = {
        "building_id": building_id,
        "structural_components": list(structural_components),
    }

    return render(
        request, "pages/building/structural_info/assemblies_list.html", context
    )  # Partial update for DELETE


def get_assemblies(assembly_list: list[BuildingAssembly]):
    impact_list = []
    structural_components = []
    for b_assembly in assembly_list:
        assembly_impact_list = []
        for p in b_assembly.assembly.product_set.all():
            assembly_impact_list.extend(
                calculate_impacts(b_assembly.assembly.dimension, b_assembly.quantity, p)
            )

        # get GWP impact for each assembly to display in list
        gwpa1a3 = [
            i["impact_value"]
            for i in assembly_impact_list
            if i["impact_type"].impact_category == "gwp"
            and i["impact_type"].life_cycle_stage == "a1a3"
        ]
        structural_components.append(
            {
                "assemblybuilding_id": b_assembly.pk,
                "assembly_name": b_assembly.assembly.name,
                "assembly_classification": b_assembly.assembly.classification.category,
                "quantity": b_assembly.quantity,
                "impacts": sum(gwpa1a3),
                "unit": DIMENSION_UNIT_MAPPING.get(b_assembly.assembly.dimension),
            }
        )
        impact_list.extend(assembly_impact_list)

    return structural_components, impact_list
