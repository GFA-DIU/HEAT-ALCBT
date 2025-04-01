import logging

from django.db import transaction
from django.db.models import Prefetch
from django.http import HttpResponseServerError
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_http_methods

from pages.forms.building_detailed_info import BuildingDetailedInformation
from pages.forms.building_general_info import BuildingGeneralInformation
from pages.forms.epds_filter_form import EPDsFilterForm
from pages.models.assembly import DIMENSION_UNIT_MAPPING
from pages.models.building import (
    Building,
    BuildingAssembly,
    BuildingAssemblySimulated,
    OperationalProduct,
    SimulatedOperationalProduct,
)
from pages.models.epd import EPD
from pages.views.assembly.epd_filtering import get_filtered_epd_list
from pages.views.building.impact_calculation import calculate_impact_operational, calculate_impacts


logger = logging.getLogger(__name__)


@require_http_methods(["GET", "POST", "DELETE"])
def building(request, building_id=None):
    logger.info("Building - Request method: %s, user: %s", request.method, request.user)

    # General Info
    if request.method == "POST":
        if request.POST.get("action") == "general_information":
            return handle_information_submit(request, building_id, True)
        if request.POST.get("action") == "detailed_information":
            return handle_information_submit(request, building_id, False)

    elif request.method == "DELETE":
        return handle_assembly_delete(request, building_id, simulation=False)

    # Full reload
    elif building_id:
        context, form, detailedForm = handle_building_load(
            request, building_id, simulation=False
        )

    else:
        # Blank for new building
        context = {
            "building_id": None,
            "building": None,
            "structural_components": [],
        }
        form = BuildingGeneralInformation()
        detailedForm = BuildingDetailedInformation()

    context["form_general_info"] = form
    context["form_detailed_info"] = detailedForm
    context["simulation"] = False
    # Full page load for GET request
    logger.info("Serving full item list page for GET request")
    return render(request, "pages/building/building.html", context)


def handle_building_load(request, building_id, simulation):
    if simulation:
        BuildingAssemblyModel = BuildingAssemblySimulated
        relation_name = "buildingassemblysimulated_set"
        BuildingProductModel = SimulatedOperationalProduct
        op_relation_name = "simulated_operational_products"
    else:
        BuildingAssemblyModel = BuildingAssembly
        relation_name = "buildingassembly_set"
        BuildingProductModel = OperationalProduct
        op_relation_name = "operational_products"

    building = get_object_or_404(
        Building.objects.filter(
            created_by=request.user
        ).prefetch_related(  # Ensure the building belongs to the user
            Prefetch(
                relation_name,
                queryset=BuildingAssemblyModel.objects.filter(
                    # assembly__created_by=request.user  # Ensure the assembly belongs to the user
                ).select_related("assembly"),
                to_attr="prefetched_components",
            )
        ),
        pk=building_id,
    )

    # Build structural components and impacts in one step
    structural_components, _ = get_assemblies(building.prefetched_components)

    context = {
        "building_id": building.id,
        "building": building,
        "structural_components": structural_components,
    }

    form = BuildingGeneralInformation(instance=building)
    detailedForm = BuildingDetailedInformation(instance=building)

    logger.info(
        "Found building: %s with %d structural components",
        building.name,
        len(context["structural_components"]),
    )

    return context, form, detailedForm


@transaction.atomic
def handle_information_submit(request, building_id, general):
    building = (
        get_object_or_404(Building, created_by=request.user, pk=building_id)
        if building_id
        else None
    )
    if general:
        form = BuildingGeneralInformation(
            request.POST, instance=building
        )  # Bind form to instance
    else:
        form = BuildingDetailedInformation(
            request.POST, instance=building
        )  # Bind form to instance
    try:
        if form.is_valid():
            building = form.save(commit=False)
            building.created_by = request.user
            building.save()
            logger.info(
                "User %s successfully saved building %s", request.user, building
            )
            return redirect("building", building_id=building.id)
        else:
            logger.info(
                "User %s could not save building %s. Form had following errors",
                request.user,
                building,
                form.errors,
            )
            return HttpResponseServerError()
    except Exception:
        logger.exception(
            "Submit of general information for building %s failed", building.pk
        )
        logger.info(
            "User %s could not savee building %s. From had following errors",
            request.user,
            building,
            form.errors,
        )
        return HttpResponseServerError()


@transaction.atomic
def handle_assembly_delete(request, building_id, simulation):
    if simulation:
        BuildingAssemblyModel = BuildingAssemblySimulated
    else:
        BuildingAssemblyModel = BuildingAssembly

    component_id = request.GET.get("component")
    try:
        # Get the component and delete it
        component = get_object_or_404(
            BuildingAssemblyModel, assembly__id=component_id, building__id=building_id
        )
        component.delete()
    except Exception:
        logger.exception(
            "Deletion of assembly %s for building %s failed.", component_id, building_id
        )

    # Fetch the updated list of assemblies for the building
    updated_list = BuildingAssemblyModel.objects.filter(
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
    logger.info(
        "User %s successfully deleted assembly %s - simulation %s",
        request.user,
        component_id,
        simulation,
    )
    return render(
        request, "pages/building/structural_info/assemblies_list.html", context
    )  # Partial update for DELETE


def get_assemblies(assembly_list: list[BuildingAssembly]):
    impact_list = []
    structural_components = []
    for b_assembly in assembly_list:
        assembly_impact_list = []
        for p in b_assembly.assembly.structuralproduct_set.all():
            assembly_impact_list.extend(
                calculate_impacts(
                    b_assembly.assembly.dimension,
                    b_assembly.quantity,
                    b_assembly.reporting_life_cycle,
                    p,
                )
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
                "assembly_id": b_assembly.assembly.pk,
                "assembly_name": b_assembly.assembly.name,
                "assembly_classification": (
                    b_assembly.assembly.classification.category
                    if b_assembly.assembly.classification
                    else ""
                ),
                "quantity": b_assembly.quantity,
                "impacts": sum(gwpa1a3),
                "unit": DIMENSION_UNIT_MAPPING.get(b_assembly.assembly.dimension),
                "is_boq": b_assembly.assembly.is_boq,
            }
        )
        impact_list.extend(assembly_impact_list)

    return structural_components, impact_list


def get_operational_products(operational_products):
    serialised_op_products = []
    for op_product in operational_products:
        serialised_op_products.append(
            {
                "id": op_product.id,
                "description": op_product.description,
                "quantity": op_product.quantity,
                "unit": op_product.input_unit,
            }
        )
    return serialised_op_products

def get_operational_impact(operational_products):
    op_impact_list = []
    for op_product in operational_products:
        impact = calculate_impact_operational(op_product)
        for key, value in impact.items():
            op_impact_list.append(
                {
                    "category": op_product.epd.category.name_en,
                    "impact_type": key,
                    "impact_value": value,
                }
            )
    return op_impact_list        

def get_op_product_list(request, building_id):
    # Get Operational Products and impacts
    epd_list, _ = get_filtered_epd_list(request, operational=True)
    context = {
        "building_id": building_id,
        "simulation": False,
        "epd_list": epd_list,
        "epd_filters_form": EPDsFilterForm(request.POST),
    }
    return render(
        request,
        "pages/building/operational_info/operational_product_list.html",
        context,
    )


def get_op_product(request):
    epd_id = request.POST.get("id")

    epd = get_object_or_404(EPD, pk=epd_id)
    epd.selection_quantity = 1
    epd.selection_unit = "KG"
    return render(
        request,
        "pages/building/operational_info/selected_operational_product.html",
        {"epd": epd},
    )


def handle_op_products_save(request, building_id):

    selected_epds = {}

    for key, value in request.POST.items():
        if key.startswith("material_") and "_quantity" in key:
            epd_id = key.split("_")[1]
            selected_epds[epd_id] = {
                "quantity": float(value),
                "unit": request.POST[f"material_{epd_id}_unit"],
                "description": request.POST[f"material_{epd_id}_description"],
            }
    for k, v in selected_epds.items():
        OperationalProduct.objects.create(
            epd_id=k,
            building_id=building_id,
            quantity=v.get("quantity"),
            input_unit=v.get("unit"),
            description=v.get("description"),
        )
