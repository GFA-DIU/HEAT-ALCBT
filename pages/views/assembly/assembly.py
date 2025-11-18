from datetime import datetime
import logging

from django.http import HttpResponse, JsonResponse
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from pages.forms.epds_filter_form import EPDsFilterForm
from pages.models.assembly import Assembly, AssemblyDimension, StructuralProduct
from pages.models.building import Building, BuildingAssembly, BuildingAssemblySimulated
from pages.forms.assembly_form import AssemblyForm

from pages.models.epd import EPD


from pages.views.assembly.epd_processing import SelectedEPD, get_epd_list
from pages.views.assembly.save_to_assembly import save_assembly

logger = logging.getLogger(__name__)

@login_required
@require_http_methods(["GET", "POST", "DELETE"])
def component_edit(request, assembly_id=None, building_id=None):
    """
    View to either edit an existing component or create a new one with pagination for EPDs.
    """
    # Handle template editing case when building_id is None
    if building_id is None:
        building_id = '00000000-0000-0000-0000-000000000000'
        is_template_edit = True
        logger.info(f"Template editing mode detected for assembly {assembly_id}")
    else:
        # Check if this is template editing
        template_edit_param = request.GET.get('template_edit') == 'true'
        is_dummy_building = str(building_id) == '00000000-0000-0000-0000-000000000000'
        is_template_edit = template_edit_param or is_dummy_building

    # Verify template ownership when editing template
    if is_template_edit and assembly_id:
        try:
            Assembly.objects.get(pk=assembly_id, is_template=True, created_by=request.user)
            logger.info(f"Confirmed template editing for assembly {assembly_id}")
        except Assembly.DoesNotExist:
            logger.error(
                f"Template edit failed: Assembly {assembly_id} is not a template or not owned by user {request.user}")

            return redirect('assembly_template_management')

    logger.info(f"Template edit mode: {is_template_edit}, assembly_id: {assembly_id}")

    if is_template_edit:
        assembly, building, context = set_up_template_edit_view(request, building_id, assembly_id)
    else:
        assembly, building, context = set_up_view(request, building_id, assembly_id)

    logger.info(
        "Request method: %s, user: %s, building %s, assembly: %s, simulation: %s, template_edit: %s",
        request.method,
        request.user,
        building,
        assembly,
        context["simulation"],
        is_template_edit,
    )

    if request.method == "POST" and request.POST.get("action") == "form_submission":
        return handle_assembly_submission(
            request, assembly, building, context["simulation"], is_template_edit
        )

    elif (
        request.method == "GET"
        and request.GET.get("page")
        or request.method == "POST"
        and request.POST.get("action") == "filter"
    ):
        # Handle partial rendering for HTMX
        return render(request, "pages/assembly/epd_list.html", context)

    # Open Modal in Building View
    elif request.method == "GET" and request.GET.get("add_component") == "step_1":
        return render(request, "pages/assembly/modal_step_1.html", context)

    elif request.method == "POST" and request.POST.get("action") == "select_epd":
        epd_id = request.POST.get("id")
        dimension = request.POST.get("dimension")
        dimension = dimension if dimension else AssemblyDimension.AREA

        epd = get_object_or_404(EPD, pk=epd_id)
        epd.selection_quantity = 1
        epd.selection_text, epd.selection_unit = epd.get_epd_info(dimension)
        epd.timestamp = datetime.now().strftime("%Y%m%d%H%M%S%f")
        return render(request, "pages/assembly/selected_epd.html", {"epd": epd})

    elif request.method == "POST" and request.POST.get("action") == "remove_epd":
        return HttpResponse()

    else:
        if not is_template_edit:
            context = handle_assembly_load(building_id, assembly, context)
        else:
            context = handle_template_assembly_load(assembly, context)

    return render(request, "pages/assembly/editor_own_page.html", context)

def set_up_template_edit_view(request, building_id, assembly_id):
    simulation = request.GET.get("simulation") == "True"
    
    # Get the assembly template directly (no BuildingAssembly relationship)
    assembly = get_object_or_404(Assembly, pk=assembly_id, is_template=True, created_by=request.user)
    
    # For template editing, we don't need a real building
    building = None
    
    epd_list, dimension = get_epd_list(request, assembly.dimension if assembly else AssemblyDimension.AREA, operational=False)
    
    req = request.POST if request.method == "POST" else request.GET
    context = {
        "assembly_id": assembly_id,
        "building_id": building_id,  # Keep the dummy building_id for URL consistency
        "filters": req,
        "epd_list": epd_list,
        "epd_filters_form": EPDsFilterForm(req),
        "dimension": dimension,
        "simulation": simulation,
        "template_edit": True,  # Flag to indicate template editing mode
    }
    return assembly, building, context


def set_up_view(request, building_id, assembly_id):
    """Fetch objects and create baseline context."""
    simulation = request.GET.get("simulation") == "True"
    template_id = request.GET.get("template_id")
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

    template_assembly = None
    if template_id and not assembly_id:
        try:
            template_assembly = get_object_or_404(Assembly, pk=template_id, is_template=True)
            logger.info(f"Loading template {template_id} for new assembly creation")
        except Assembly.DoesNotExist:
            logger.warning(f"Template {template_id} not found or not a template")

    epd_list, dimension = get_epd_list(request, assembly.dimension if assembly else (template_assembly.dimension if template_assembly else AssemblyDimension.AREA), operational=False)

    req = request.POST if request.method == "POST" else request.GET
    context = {
        "assembly_id": assembly_id,
        "building_id": building_id,
        "filters": req,
        "epd_list": epd_list,
        "epd_filters_form": EPDsFilterForm(req),
        "dimension": dimension,
        "simulation": simulation,
        "template_assembly": template_assembly,  # Add template data to context
    }
    return assembly, building, context


def handle_assembly_submission(request, assembly, building, simulation, is_template_edit=False):
    # Get template_id if this is a new assembly created from template
    # Check POST data for template_id from hidden form field
    template_id = None if assembly else request.POST.get("template_id")
    save_assembly(request, assembly, building, simulation, is_template_edit=is_template_edit, template_id=template_id)

    response = JsonResponse({"message": "Redirecting"})

    if is_template_edit:
        # Redirect to template management page after editing template
        response["HX-Redirect"] = reverse("assembly_template_management")
    elif simulation:
        response["HX-Redirect"] = reverse(
            "building_simulation", kwargs={"building_id": building.pk}
        )
    else:
        response["HX-Redirect"] = reverse(
            "building", kwargs={"building_id": building.pk}
        )

    return response

def handle_assembly_load(building_id, assembly, context):
    template_assembly = context.get("template_assembly")

    source_assembly = assembly or template_assembly

    if source_assembly:
        products = (
            StructuralProduct.objects
            .filter(assembly=source_assembly)
            .select_related(
                "epd",
                "epd__category",
                "epd__country",
                "classification",
            )
        )

        selected_epds = [SelectedEPD.parse_product(p) for p in products]
        context["selected_epds"] = selected_epds
        context["selected_epds_ids"] = [
            selected_epd.id for selected_epd in selected_epds
        ]

    # Pre-populate form with template data if creating from template
    if template_assembly and not assembly:
        context["form"] = AssemblyForm(
            instance=template_assembly,
            building_id=building_id,
            simulation=context.get("simulation")
        )
        context["form"].initial["name"] = f"{template_assembly.name} (Copy)"
        context["form"].initial["is_template"] = False
        context["using_template"] = True
    else:
        context["form"] = AssemblyForm(
            instance=assembly, building_id=building_id, simulation=context.get("simulation")
        )

    context["dimension"] = source_assembly.dimension if source_assembly else AssemblyDimension.AREA

    return context


def handle_template_assembly_load(assembly, context):
    if assembly:
        products = (
            StructuralProduct.objects
            .filter(assembly=assembly)
            .select_related(
                "epd",
                "epd__category",
                "epd__country",
                "classification",
            )
        )

        selected_epds = [SelectedEPD.parse_product(p) for p in products]
        context["selected_epds"] = selected_epds
        context["selected_epds_ids"] = [
            selected_epd.id for selected_epd in selected_epds
        ]

    # For templates, we use dummy building_id and set template_edit=True to avoid BuildingAssembly lookup
    context["form"] = AssemblyForm(
        instance=assembly,
        building_id='00000000-0000-0000-0000-000000000000',
        simulation=context.get("simulation"),
        template_edit=True
    )
    context["dimension"] = assembly.dimension if assembly else AssemblyDimension.AREA

    return context