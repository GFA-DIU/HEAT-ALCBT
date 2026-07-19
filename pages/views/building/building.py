import json
import logging

from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Prefetch
from django.http import HttpResponse, HttpResponseServerError
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from pages.forms.building_detailed_info import BuildingDetailedInformation
from pages.forms.building_general_info import BuildingGeneralInformation
from pages.forms.epds_filter_form import EPDsFilterForm
from pages.forms.operational_info_form import OperationalInfoForm
from pages.models.assembly import DIMENSION_UNIT_MAPPING, StructuralProduct
from pages.models.building import (Building, BuildingAssembly,
                                   BuildingAssemblySimulated,
                                   OperationalProduct,
                                   SimulatedOperationalProduct)
from pages.models.epd import EPDImpact, MaterialCategory
from pages.views.assembly.epd_processing import get_epd_list
from pages.views.building.building_stats import (
    get_building_chart_data, get_building_detail_statistics)
from pages.views.building.embodied_benchmark_data import (
    get_benchmark_for_building, calculate_benchmark_position)
from pages.views.building.impact_calculation import calculate_impacts
from pages.views.building.operational_products.operational_products import (
    get_op_product, get_op_product_list, handle_op_products_save,
    serialize_operational_products)

logger = logging.getLogger(__name__)


@login_required
@require_http_methods(["GET", "POST", "DELETE"])
def building(request, building_id=None):
    logger.info("Building - Request method: %s, user: %s", request.method, request.user)

    # General Info
    if request.method == "POST":
        match request.POST.get("action"):
            case "general_information":
                return handle_information_submit(request, building_id, "general")
            case "detailed_information":
                return handle_information_submit(request, building_id, "detailed")
            case "operational_info":
                return handle_information_submit(request, building_id, "operational")
            case "filter":
                return get_op_product_list(request, building_id)
            case "select_op_product":
                return get_op_product(request, building_id)
            case "save_op_products":
                handle_op_products_save(request, building_id)
                context, form, detailedForm, _ = handle_building_load(
                    request, building_id, simulation=False
                )
                context["edit_mode"] = False
                response = render(
                    request,
                    "pages/building/operational_info/operational_product_list.html",
                    context,
                )
                response["HX-Refresh"] = "true"  # Add the HX-Refresh header
                return response
            case "edit_products":
                context, _, _, _ = handle_building_load(
                    request, building_id, simulation=False
                )
                context["edit_mode"] = True
                return render(
                    request,
                    "pages/building/operational_info/operational_products.html",
                    context,
                )
            case _:
                logger.info("No action defined for the POST request")

    elif request.method == "DELETE":
        if request.GET.get("op_product_id"):
            response = HttpResponse()
            response['HX-Trigger-After-Swap'] = 'componentDeleted'
            return response
        if request.GET.get("component"):
            return handle_assembly_delete(request, building_id, simulation=False)
    elif request.method == "GET":
        if request.GET.get("page"):
            return get_op_product_list(request, building_id)
        # Full reload
        if building_id:
            context, form, detailedForm, operationalInfoForm = handle_building_load(
                request, building_id, simulation=False
            )
        else:
            # Blank for new building
            context = {
                "building_id": None,
                "building": None,
                "structural_components": [],
                "edit_mode": False,
            }
            form = BuildingGeneralInformation()
            detailedForm = BuildingDetailedInformation()
            operationalInfoForm = OperationalInfoForm()

    context["form_general_info"] = form
    context["form_detailed_info"] = detailedForm
    context["form_operational_info"] = operationalInfoForm

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
        Building.objects
            .filter(created_by=request.user)
            .select_related("energy_summary")
            .prefetch_related(
                # 1) grab each BuildingAssemblyModel …
                Prefetch(
                    relation_name,
                    queryset=BuildingAssemblyModel.objects
                        .filter(building__created_by=request.user)
                        .select_related("assembly")                           # pull in the Assembly in same query
                        .order_by("-assembly__created_at")
                        .prefetch_related(
                            # 2) … and on *each* BuildingAssemblyModel, pull its assembly's products …
                            Prefetch(
                                "assembly__structuralproduct_set",
                                queryset=StructuralProduct.objects
                                    .select_related("epd", "classification")
                                    .prefetch_related(
                                        # 3) … and on each product’s EPD, grab its impacts …
                                        Prefetch(
                                            "epd__epdimpact_set",
                                            queryset=EPDImpact.objects.select_related("impact"),
                                            to_attr="all_impacts",
                                        ),
                                        # 4) … and also fetch the categories to avoid extra queries
                                        "epd__category",
                                        "classification__category",
                                    ),
                                to_attr="prefetched_products",       # <–– now Assembly.products is that list
                            ),
                        ),
                    to_attr="prefetched_components",  # <–– Building.prefetched_components is list of BuildingAssemblyModel
                ),
                # 5) plus grab any BuildingProductModel in one go
                Prefetch(
                    op_relation_name,
                    queryset=BuildingProductModel.objects.all(),
                    to_attr="prefetched_operational_products",
                ),
            ),
        pk=building_id,
    )

    # Build structural components and impacts in one step
    structural_components, _ = get_assemblies(building.prefetched_components)

    # Get Operational Products and impacts
    operational_products = serialize_operational_products(
        building.prefetched_operational_products
    )

    # Get Operational Products and impacts
    epd_list, _ = get_epd_list(request, None, operational=True)
    form = EPDsFilterForm(request.POST)
    op_field_fix = {
        "category": "Others",
        "subcategory": "Energy carrier - delivery free user",
    }
    for field, value in op_field_fix.items():
        form.fields[field].queryset = MaterialCategory.objects
        initial = MaterialCategory.objects.get(name_en=value)
        form.fields[field].initial = initial
        form.fields[field].disabled = True

    form.fields["childcategory"].queryset = MaterialCategory.objects.filter(
        parent=initial
    )

    # Check energy mismatch between energy summary and carrier totals
    from decimal import Decimal as _D
    from django.db.models import Sum as _Sum
    energy_summary = getattr(building, 'energy_summary', None)
    systems_total_kwh = _D(str(energy_summary.total_kwh)) if energy_summary and energy_summary.total_kwh else _D('0')
    carriers_total_kwh = _D(str(
        OperationalProduct.objects.filter(building=building, input_unit='kwh')
        .aggregate(t=_Sum('quantity'))['t'] or 0
    ))
    _tol = max(_D('2000'), systems_total_kwh * _D('0.05'))
    energy_mismatch = (systems_total_kwh > 0 or carriers_total_kwh > 0) and abs(systems_total_kwh - carriers_total_kwh) > _tol

    # Calculate statistics and chart data for building detail page using already-prefetched data
    building_stats = get_building_detail_statistics(
        building,
        prefetched_assemblies=building.prefetched_components,
        prefetched_operational=building.prefetched_operational_products,
    )
    chart_data = get_building_chart_data(
        building,
        prefetched_assemblies=building.prefetched_components,
        prefetched_operational=building.prefetched_operational_products,
    )

    benchmark = get_benchmark_for_building(building)
    benchmark_position = calculate_benchmark_position(
        building_stats.get('total_embodied_carbon', 0), benchmark
    )

    context = {
        "building_id": building.id,
        "building": building,
        "structural_components": structural_components,
        "operational_products": operational_products,
        "has_structural": bool(structural_components),
        "has_operational": bool(operational_products),
        "epd_list": epd_list,
        "epd_filters_form": form,
        "edit_mode": False,
        "simulation": simulation,
        # Statistics for building detail page
        "stats": building_stats,
        "calculation_errors": building_stats.get('calculation_errors', []),
        "chart_data": json.dumps(chart_data),  # Convert to JSON for JavaScript
        # Benchmark and savings data for export card and savings tab
        "benchmark": benchmark,
        "benchmark_position": benchmark_position,
        "embodied_savings": chart_data.get("embodied_savings", {}),
        # Operational (Layer 1 benchmark + Layer 3 measures) for savings tab
        "operational_benchmark_position": chart_data.get("operational_benchmark_position"),
        "operational_savings": chart_data.get("operational_savings", {}),
        "energy_mismatch": energy_mismatch,
        "energy_mismatch_systems_kwh": float(systems_total_kwh),
        "energy_mismatch_carriers_kwh": float(carriers_total_kwh),
        "design_drawings_status": building.design_drawings_status,
        "boq_status": building.boq_status,
    }

    form = BuildingGeneralInformation(instance=building)
    detailedForm = BuildingDetailedInformation(instance=building)
    operationalInfoForm = OperationalInfoForm(instance=building)

    logger.info(
        "Found building: %s with %d structural components",
        building.name,
        len(context["structural_components"]),
    )

    return context, form, detailedForm, operationalInfoForm


@transaction.atomic
def handle_information_submit(request, building_id, form):
    building = (
        get_object_or_404(Building, created_by=request.user, pk=building_id)
        if building_id
        else None
    )
    match form:
        case "general":
            form = BuildingGeneralInformation(
                request.POST, instance=building
            )  # Bind form to instance
        case "detailed":
            form = BuildingDetailedInformation(
                request.POST, instance=building
            )  # Bind form to instance
        case "operational":
            form = OperationalInfoForm(
                request.POST, instance=building
            )  # Bind form to instance
    try:
        if form.is_valid():
            building = form.save(commit=False)
            building.created_by = request.user
            building.save()

            logger.info(
                "User %s successfully saved building %s (UUID: %s)", request.user, building, building.uuid
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
    updated_list = (
        BuildingAssemblyModel.objects
            .filter(
                building__created_by=request.user,
                assembly__created_by=request.user,
                building_id=building_id,
            )
            .select_related("assembly", "building")
            .order_by("-assembly__created_at")
            .prefetch_related(
                # 1: Grab each StructuralProduct on assembly
                Prefetch(
                    "assembly__structuralproduct_set",
                    queryset=StructuralProduct.objects
                        .select_related("epd", "classification")
                        .prefetch_related(
                            # 2: Within each EPD, grab its impacts
                            Prefetch(
                                "epd__epdimpact_set",
                                queryset=EPDImpact.objects.select_related("impact"),
                                to_attr="all_impacts",
                            ),
                            # 3: Also fetch the categories to avoid extra queries
                            "epd__category",
                            "classification__category",
                        ),
                    to_attr="prefetched_products",  # <-- this will be assembly.products
                ),
            )
    )
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
    response = render(
        request, "pages/building/structural_info/assemblies_list.html", context
    )
    response["HX-Trigger-After-Swap"] = "componentDeleted"
    
    return response

def get_assemblies(assembly_list: list[BuildingAssembly]):
    impact_list = []
    structural_components = []
    for b_assembly in assembly_list:
        assembly_impact_list = []
        for p in getattr(b_assembly.assembly, "prefetched_products", []):
            try:
                assembly_impact_list.extend(
                    calculate_impacts(
                        b_assembly.assembly.dimension,
                        b_assembly.quantity,
                        b_assembly.building.total_floor_area,
                        p,
                    )
                )
            except (ValueError, AttributeError, ZeroDivisionError):
                continue

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

def savings_tab(request, building_id):
    if request.method == "GET":
        context, _, _, _ = handle_building_load(request, building_id, simulation=False)
        return render(request, "pages/building/savings_tab.html", context)