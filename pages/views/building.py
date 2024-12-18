import logging

from django.db.models import Prefetch, Q
from django.http import HttpResponseServerError
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_http_methods

from pages.forms.building_general_info import BuildingGeneralInformation
from pages.models.building import Building, BuildingAssembly
from pages.models.assembly import AssemblyImpact

from cities_light.models import City
from pages.scripts.dashboards.building_dashboard import building_dashboard

logger = logging.getLogger(__name__)


@require_http_methods(["GET", "POST", "DELETE"])
def building(request, building_id = None):
    print("request user", request.user)
    # General Info
    if request.method == "POST" and request.POST.get("action") == "general_information":
        building = get_object_or_404(Building, created_by=request.user, pk=building_id) if building_id else None
        form = BuildingGeneralInformation(
            request.POST, instance=building
        )  # Bind form to instance
        if form.is_valid():
            print("these fields changed", form.changed_data)
            building = form.save(commit=False)
            building.created_by = request.user
            building.save()
            print("Building updated in DB:", building)
        else:
            print("Form is invalid")
            print("Errors:", form.errors)
            return HttpResponseServerError()

        return redirect("building", building_id=building.id)

    elif request.method == "DELETE":
        component_id = request.GET.get("component")
        # component = get_object_or_404(BuildingAssembly, id=item_to_delete)
        # component.delete()
        # context["structural_components"] = [c for c in structural_components if str(c["assembly_id"]) != item_to_delete]
        # print("context: ", context)
        # Get the component and delete it
        component = get_object_or_404(BuildingAssembly, id=component_id)
        component.delete()

        # Fetch the updated list of assemblies for the building
        updated_list = BuildingAssembly.objects.filter(
            building__created_by=request.user,
            assembly__created_by=request.user,
            building_id=building_id,
        ).select_related(
            "assembly"
        )  # Optimize query by preloading related Assembly
        structural_components = []
        for component in updated_list:
            impacts = [
                {
                    "impact_id": impact.impact.id,
                    "impact_name": impact.impact.name,
                    "value": impact.value,
                }
                for impact in component.assembly.assemblyimpact_set.all()
            ]

            structural_components.append(
                {
                    "assemblybuilding_id": component.id,
                    "assembly_name": component.assembly.name,
                    "assembly_classification": component.assembly.classification,
                    "quantity": component.quantity,
                    "unit": component.unit,
                    "impacts": impacts,
                }
            )
        context = {
            "building_id": building_id,
            "structural_components": list(structural_components),
        }
        return render(
            request, "pages/building/structural_info/assemblies_list.html", context
        )  # Partial update for DELETE
    elif request.GET.get("country"):
        cities = City.objects.filter(
            country_id=request.GET.get("country")
        ).order_by("name")
        return render(request, "pages/utils/city_select.html", {"cities": cities})
    # Full reload
    elif building_id:
        building = get_object_or_404(
            Building.objects.filter(
                created_by=request.user
            ).prefetch_related(  # Ensure the building belongs to the user
                Prefetch(
                    "buildingassembly_set",
                    queryset=BuildingAssembly.objects.filter(
                        # assembly__created_by=request.user  # Ensure the assembly belongs to the user
                    )
                    .select_related("assembly")
                    .prefetch_related(
                        Prefetch(
                            "assembly__assemblyimpact_set",
                            queryset=AssemblyImpact.objects.select_related("impact"),
                        )
                    ),
                    to_attr="prefetched_components",
                )
            ),
            pk=building_id,
        )

        # Build structural components and impacts in one step
        structural_components = []
        for component in building.prefetched_components:
            impacts = [
                {
                    "impact_id": impact.impact.id,
                    "impact_name": impact.impact.__str__(),
                    "value": impact.value,
                }
                for impact in component.assembly.assemblyimpact_set.all()
            ]

            structural_components.append(
                {
                    "assemblybuilding_id": component.id,
                    "assembly_name": component.assembly.name,
                    "assembly_classification": component.assembly.classification,
                    "quantity": component.quantity,
                    "unit": component.unit,
                    "impacts": impacts,
                }
            )

        context = {
            "building_id": building.id,
            "building": building,
            "structural_components": list(structural_components),
        }
        if len(structural_components):
            context["dashboard"] = building_dashboard(structural_components)

        form = BuildingGeneralInformation(instance=building)

        logger.info(
            "Found building: %s with %d structural components",
            building.name,
            len(context["structural_components"]),
        )
    else:
        context = {
            "building_id": None,
            "building": None,
            "structural_components": [],
        }
        form = BuildingGeneralInformation()
    context["form_general_info"] = form
    # Full page load for GET request
    logger.info("Serving full item list page for GET request")
    return render(request, "pages/building/building.html", context)
