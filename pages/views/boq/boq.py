import logging

from django.http import HttpResponse, JsonResponse
from django.shortcuts import render, get_object_or_404
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from pages.forms.boq_assembly_form import BOQAssemblyForm
from pages.forms.epds_filter_form import EPDsFilterForm
from pages.models.assembly import AssemblyCategory, AssemblyDimension, StructuralProduct
from pages.models.building import Building, BuildingAssembly, BuildingAssemblySimulated

from pages.models.epd import EPD
from pages.views.assembly.epd_processing import SelectedEPD, get_epd_list
from pages.views.assembly.save_to_assembly import save_assembly

logger = logging.getLogger(__name__)


@require_http_methods(["GET", "POST", "DELETE"])
def boq_edit(request, building_id, assembly_id=None):
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

        epd = get_object_or_404(EPD, pk=epd_id)
        epd.selection_quantity = 1
        epd.selection_text = "Quantity"
        epd.selection_unit = epd.declared_unit

        categories = AssemblyCategory.objects.all()

        return render(
            request,
            "pages/assembly/selected_epd.html",
            {"epd": epd, "categories": categories, "is_boq": True},
        )

    elif request.method == "POST" and request.POST.get("action") == "remove_epd":
        return HttpResponse()

    context = handle_assembly_load(building_id, assembly, context)
    # Render full template for non-HTMX requests
    return render(request, "pages/assembly/boq.html", context)


def set_up_view(request, building_id, assembly_id):
    """Fetch objects and create baseline context."""
    simulation = request.GET.get("simulation", "false").lower() == "true"
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
        assert assembly.is_boq
    else:
        building = get_object_or_404(Building, pk=building_id)
        assembly = None

    epd_list, dimension = get_epd_list(request, None)
    context = {
        "assembly_id": assembly_id,
        "building_id": building_id,
        "epd_list": epd_list,
        "epd_filters_form": EPDsFilterForm(request.POST),
        "dimension": dimension,  # Is also required for full reload
        "simulation": simulation,
    }
    return assembly, building, context


def handle_assembly_submission(request, assembly, building, simulation):
    save_assembly(request, assembly, building, simulation, is_boq=True)
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
        products = StructuralProduct.objects.filter(assembly=assembly).select_related(
            "epd"
        )
        selected_epds = [SelectedEPD.parse_product(p, True) for p in products]
        context["selected_epds"] = selected_epds
        context["selected_epds_ids"] = [
            selected_epd.id for selected_epd in selected_epds
        ]
    context["is_boq"] = True
    context["categories"] = AssemblyCategory.objects.all()
    context["form"] = BOQAssemblyForm(
        instance=assembly, building_id=building_id, simulation=context.get("simulation")
    )
    context["dimension"] = assembly.dimension if assembly else AssemblyDimension.AREA

    return context
