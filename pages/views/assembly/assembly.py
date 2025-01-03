import logging

from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from pages.forms.epds_filter_form import EPDsFilterForm
from pages.models.assembly import Assembly, AssemblyDimension, Product
from pages.models.building import Building, BuildingAssembly
from pages.forms.assembly_form import AssemblyForm

from pages.views.assembly.epd_processing import SelectedEPD, get_epd_list
from pages.views.assembly.save_to_assembly import save_assembly

logger = logging.getLogger(__name__)


@require_http_methods(["GET", "POST", "DELETE"])
def component_edit(request, building_id, assembly_id=None):
    """
    View to either edit an existing component or create a new one with pagination for EPDs.
    """
    component = None
    if assembly_id:
        building_assembly = get_object_or_404(
            BuildingAssembly.objects.select_related(),
            assembly_id=assembly_id,
            building_id=building_id,
        )
        # If there's non it will already throw an error so no need for checking
        component = building_assembly.assembly
    context = {
        "assembly_id": assembly_id,
        "building_id": building_id,
        "epd_list": get_epd_list(request, component),
        "epd_filters_form": EPDsFilterForm(request.POST),
        "dimension": request.POST.get("dimension"),
    }
    building_instance = get_object_or_404(Building, pk=building_id)

    if request.method == "POST" and request.POST.get("action") == "form_submission":
        if not component:
            component = Assembly()
        save_assembly(request, component, building_instance)
        # The redirect shortcut is not working properly with HTMX
        # return redirect("building", building_id=building_instance.id)
        # instead use the following:
        response = JsonResponse({"message": "Redirecting"})
        response["HX-Redirect"] = reverse(
            "building", kwargs={"building_id": building_id}
        )
        return response

    elif (
        request.method == "GET"
        and request.GET.get("page")
        or request.method == "POST"
        and request.POST.get("action") == "filter"
    ):
        # Handle partial rendering for HTMX
        return render(request, "pages/building/component_add/epd_list.html", context)

    elif request.method == "GET" and request.GET.get("add_component") == "step_1":
        # TODO: Only makes sense for new component
        return render(
            request, "pages/building/component_add/modal_step_1.html", context
        )

    else:
        if component:
            products = Product.objects.filter(assembly=component).select_related("epd")
            selected_epds = [SelectedEPD.parse_product(p) for p in products]
            context["selected_epds"] = selected_epds
        context["form"] = AssemblyForm(instance=component, building_id=building_id)
        context["dimension"] = (
            component.dimension if component else AssemblyDimension.AREA
        )

    # Render full template for non-HTMX requests
    return render(request, "pages/building/component_add/editor_own_page.html", context)
