import logging

from django.http import HttpResponse, JsonResponse
from django.shortcuts import render, get_object_or_404
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from pages.forms.epds_filter_form import EPDsFilterForm
from pages.models.assembly import Assembly, AssemblyDimension, Product
from pages.models.building import Building, BuildingAssembly, BuildingAssemblySimulated
from pages.forms.assembly_form import AssemblyForm

from pages.models.epd import EPD
from pages.views.assembly.epd_filtering import get_epd_dimension_info
from pages.views.assembly.epd_processing import SelectedEPD, get_epd_list
from pages.views.assembly.save_to_assembly import save_assembly

logger = logging.getLogger(__name__)


@require_http_methods(["GET", "POST", "DELETE"])
def component_edit(request, building_id, assembly_id=None):
    """
    View to either edit an existing component or create a new one with pagination for EPDs.
    """
    assembly, building, context = set_up_view(request, building_id, assembly_id)

    if request.method == "POST" and request.POST.get("action") == "form_submission":
        return handle_assembly_submission(request, assembly, building, context["simulation"])

    # Update EPD List
    elif (
        request.method == "GET"
        and request.GET.get("page")
        or request.method == "POST"
        and request.POST.get("action") == "filter"
    ):
        # Handle partial rendering for HTMX
        # TODO: consider moving page logic and filtering out of "set-up"
        return render(request, "pages/assembly/epd_list.html", context)


    # Open Modal in Building View
    elif request.method == "GET" and request.GET.get("add_component") == "step_1":
        # TODO: Only makes sense for new component, maybe make part of Building view?
        return render(request, "pages/building/assembly/modal_step_1.html", context)

    elif request.method == "POST" and request.POST.get("action") == "select_epd":
        # TODO: Only makes sense for new component
        epd_id = request.POST.get("id")
        dimension = request.POST.get("dimension")
        dimension = dimension if dimension else AssemblyDimension.AREA

        epd = get_object_or_404(EPD, pk=int(epd_id))
        epd.sel_quantity = 1
        epd.selection_text, epd.sel_unit = get_epd_dimension_info(dimension, epd.declared_unit)
        return render(request, "pages/assembly/selected_epd_list.html", {"epd": epd})

    elif request.method == "POST" and request.POST.get("action") == "remove_epd":
        # TODO: Only makes sense for new component
        return HttpResponse()

    else:
        context = handle_assembly_load(building_id, assembly, context)

    # Render full template for non-HTMX requests
    return render(request, "pages/assembly/editor_own_page.html", context)


def set_up_view(request, building_id, assembly_id):
    """Fetch objects and create baseline context."""
    simulation = request.GET.get('simulation', 'false').lower() == 'true'
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

    context = {
        "assembly_id": assembly_id,
        "building_id": building_id,
        "epd_list": get_epd_list(request, assembly),
        "epd_filters_form": EPDsFilterForm(request.POST),
        "dimension": request.POST.get("dimension"),  # TODO: do I need this here already?
        "simulation": simulation,
    }
    return assembly, building, context


def handle_assembly_submission(request, assembly, building, simulation):
    if not assembly:
        assembly = Assembly()
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
        products = Product.objects.filter(assembly=assembly).select_related("epd")
        selected_epds = [SelectedEPD.parse_product(p) for p in products]
        context["selected_epds"] = selected_epds
        context["selected_epds_ids"] = [selected_epd.id for selected_epd in selected_epds]
    context["form"] = AssemblyForm(instance=assembly, building_id=building_id, simulation=context.get("simulation"))
    context["dimension"] = (
            assembly.dimension if assembly else AssemblyDimension.AREA
        )

    return context
