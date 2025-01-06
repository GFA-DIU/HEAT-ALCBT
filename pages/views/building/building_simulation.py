import logging

from django.shortcuts import render, redirect
from django.views.decorators.http import require_http_methods

from pages.models.building import BuildingAssembly, BuildingAssemblySimulated
from pages.views.building.building import handle_building_load
from pages.views.building.building import handle_assembly_delete


logger = logging.getLogger(__name__)


@require_http_methods(["GET", "POST", "DELETE"])
def building_simulation(request, building_id):
    logger.info("Building Simulation - Request method: %s, user: %s", request.method, request.user)

    if request.method == "DELETE":
        return handle_assembly_delete(request, building_id)
    
    elif request.method == "POST" and request.POST.get("action") == "reset":
        return handle_simulation_reset(building_id)

    # Full reload
    else:
        context, form = handle_building_load(request, building_id, simulation=True)
        
        if not context["structural_components"]:
            return handle_simulation_reset(building_id)
        
        # disable the form fields and button
        for field in form.fields:
            form.fields[field].disabled = True
        
        form.helper.layout[4].flat_attrs = "disabled"

        context["form_general_info"] = form
        
    context["simulation"] = True
    # Full page load for GET request
    logger.info("Serving full item list page for GET request")
    return render(request, "pages/building/building_simulation.html", context)


def handle_simulation_reset(building_id):
    # TODO: this needs create new assemblies for assemblies mode=Custom
    # create clean slate
    BuildingAssemblySimulated.objects.filter(building__id=building_id).delete()
    
    normal_assemblies = BuildingAssembly.objects.filter(building__id=building_id)
    
    if not normal_assemblies:
        # simulation is not possible if there is normal set-up
        return redirect("building", building_id=building_id)
    
    for a in normal_assemblies:
        BuildingAssemblySimulated.objects.create(
            assembly=a.assembly,
            building=a.building,
            quantity=a.quantity
        )
    
    # Do a full page reload
    return redirect("building_simulation", building_id=building_id)