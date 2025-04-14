from datetime import datetime
import logging

from django.http import HttpResponse, JsonResponse
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from pages.forms.epds_filter_form import EPDsFilterForm
from pages.models.assembly import Assembly, AssemblyDimension, StructuralProduct
from pages.models.building import Building, BuildingAssembly, BuildingAssemblySimulated
from pages.forms.assembly_form import AssemblyForm

from pages.models.epd import EPD
from pages.views.assembly.epd_filtering import get_epd_info


from pages.views.assembly.epd_processing import SelectedEPD, get_epd_list
from pages.views.assembly.save_to_assembly import save_assembly

logger = logging.getLogger(__name__)

@login_required
@require_http_methods(["GET", "POST", "DELETE"])
def component_edit(request, building_id, assembly_id=None):
    """
    View to either edit an existing component or create a new one with pagination for EPDs.
    """
    assembly, building, context = set_up_view(request, building_id, assembly_id)
    logger.info(
        "Building - Request method: %s, user: %s, building %s, assembly: %s, simulation: %s",
        request.method,
        request.user,
        building,
        assembly,
        context["simulation"],
    )

    if request.method == "POST" and request.POST.get("action") == "form_submission":
        return handle_assembly_submission(
            request, assembly, building, context["simulation"]
        )

    # Update EPD List
    elif (
        request.method == "GET"
        and request.GET.get("page")
        or request.method == "POST"
        and request.POST.get("action") == "filter"
    ):
        # Handle partial rendering for HTMX
        # Does not need own logic since filtering is also part of full-load
        return render(request, "pages/assembly/epd_list.html", context)

    # Open Modal in Building View
    elif request.method == "GET" and request.GET.get("add_component") == "step_1":
        # TODO: Only makes sense for new component, maybe make part of Building view?
        return render(request, "pages/assembly/modal_step_1.html", context)

    elif request.method == "POST" and request.POST.get("action") == "select_epd":
        epd_id = request.POST.get("id")
        dimension = request.POST.get("dimension")
        dimension = dimension if dimension else AssemblyDimension.AREA

        epd = get_object_or_404(EPD, pk=epd_id)
        epd.selection_quantity = 1
        epd.selection_text, epd.selection_unit = get_epd_info(
            dimension, epd.declared_unit
        )
        epd.timestamp = datetime.now().strftime("%Y%m%d%H%M%S%f")
        return render(request, "pages/assembly/selected_epd.html", {"epd": epd})

    elif request.method == "POST" and request.POST.get("action") == "remove_epd":
        return HttpResponse()

    else:
        context = handle_assembly_load(building_id, assembly, context)

    # Render full template for non-HTMX requests
    return render(request, "pages/assembly/editor_own_page.html", context)


def set_up_view(request, building_id, assembly_id):
    """Fetch objects and create baseline context."""
    simulation = request.GET.get("simulation") == "True"
    if simulation:
        BuildingAssemblyModel = BuildingAssemblySimulated
    else:
        BuildingAssemblyModel = BuildingAssembly

    if assembly_id:
        building_assembly = get_object_or_404(
            BuildingAssemblyModel.objects.select_related(),
            assembly_id=assembly_id,
            building_id=building_id,
        )
        building = building_assembly.building
        assembly = building_assembly.assembly
    else:
        building = get_object_or_404(Building, pk=building_id)
        assembly = None


    epd_list, dimension = get_epd_list(request, assembly.dimension if assembly else AssemblyDimension.AREA, operational=False)

    req = request.POST if request.method == "POST" else request.GET
    context = {
        "assembly_id": assembly_id,
        "building_id": building_id,
        "filters": req,
        "epd_list": epd_list,
        "epd_filters_form": EPDsFilterForm(req),
        "dimension": dimension,  # Is also required for full reload
        "simulation": simulation,
    }
    return assembly, building, context


def handle_assembly_submission(request, assembly, building, simulation):
    save_assembly(request, assembly, building, simulation)
    # The redirect shortcut is not working properly with HTMX
    # return redirect("building", building_id=building_instance.id)
    # instead use the following:
    response = JsonResponse({"message": "Redirecting"})
    if simulation:
        response["HX-Redirect"] = reverse(
            "building_simulation", kwargs={"building_id": building.pk}
        )
    else:
        response["HX-Redirect"] = reverse(
            "building", kwargs={"building_id": building.pk}
        )

    return response


def handle_assembly_load(building_id, assembly, context):
    if assembly:
        products = StructuralProduct.objects.filter(assembly=assembly).select_related("epd")
        selected_epds = [SelectedEPD.parse_product(p) for p in products]
        context["selected_epds"] = selected_epds
        context["selected_epds_ids"] = [
            selected_epd.id for selected_epd in selected_epds
        ]
    context["form"] = AssemblyForm(
        instance=assembly, building_id=building_id, simulation=context.get("simulation")
    )
    context["dimension"] = assembly.dimension if assembly else AssemblyDimension.AREA

    return context
