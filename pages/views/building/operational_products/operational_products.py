from datetime import datetime
import logging

from django.db import transaction
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, render

from pages.forms.epds_filter_form import EPDsFilterForm
from pages.models.building import OperationalProduct, SimulatedOperationalProduct
from pages.models.epd import EPD, Unit
from pages.views.assembly.epd_filtering import get_filtered_epd_list
from pages.views.building.impact_calculation import calculate_impact_operational

logger = logging.getLogger(__name__)


@transaction.atomic
def handle_op_products_save(request, building_id, simulation=False):
    if simulation:
        ProductModel = SimulatedOperationalProduct
    else:
        ProductModel = OperationalProduct

    ProductModel.objects.filter(building_id=building_id).delete()
    selected_epds = {}

    for key, value in request.POST.items():
        if key.startswith("material_") and "_quantity" in key:
            key_array = key.split("_")
            epd_id = key_array[1]
            timestamp = key_array[-1]
            selected_epds[epd_id + timestamp] = {
                "id": epd_id,
                "quantity": float(value),
                "unit": request.POST[f"material_{epd_id}_unit_{timestamp}"],
                "description": request.POST[
                    f"material_{epd_id}_description_{timestamp}"
                ],
            }
    for _, v in selected_epds.items():
        ProductModel.objects.create(
            epd_id=v.get("id"),
            building_id=building_id,
            quantity=v.get("quantity"),
            input_unit=v.get("unit"),
            description=v.get("description"),
        )


def serialize_operational_products(operational_products):
    serialised_op_products = []
    for op_product in operational_products:
        impacts = calculate_impact_operational(op_product)
        serialised_op_products.append(
            {
                "id": op_product.epd.id,
                "product_id": op_product.id,
                "name": op_product.epd.name,
                "country": op_product.epd.country,
                "category": op_product.epd.category,
                "description": op_product.description,
                "selection_unit": op_product.input_unit,
                "selection_quantity": op_product.quantity,
                "timestamp": datetime.now().strftime("%Y%m%d%H%M%S%f"),
                "op_units": op_product.epd.get_op_units(),
                "source": op_product.epd.source,
                "gwp_b6": round(impacts["gwp_b6"], 2),
                "penrt_b6": round(impacts["penrt_b6"], 2),
            }
        )
    return serialised_op_products


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


def get_op_product(request, building_id):
    epd_id = request.POST.get("id")

    epd = get_object_or_404(EPD, pk=epd_id)
    epd.selection_quantity = 1
    epd.selection_unit = Unit.KG
    epd.timestamp = datetime.now().strftime("%Y%m%d%H%M%S%f")
    epd.op_units = epd.get_op_units()
    epd.product_id = None
    context = {
        "epd": epd,
        "edit_mode": True,
        "building_id": building_id,
        "category": epd.category,
    }
    return render(
        request,
        "pages/building/operational_info/selected_operational_product.html",
        context,
    )
