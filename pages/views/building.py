import logging

from dataclasses import dataclass
from django.http import HttpResponse
from django.shortcuts import render
from django.views.decorators.http import require_http_methods

from pages.forms.building_general_info import BuildingGeneralInformation
from pages.models.building import Building, Assembly

logger = logging.getLogger(__name__)


@dataclass
class StructElement:
    id: str
    name: str
    country: str
    material: str
    quantity: str
    emissions: str


@dataclass
class BuildingMock:
    name: str
    country: str
    components: list[StructElement]


item = BuildingMock(
    name="Test Building 1",
    country="New Dehli, India",
    components=[
        StructElement(
            id="1",
            name="Intermediate Floor construction",
            country="Germany",
            material="Concrete Filler Slab",
            quantity="100",
            emissions="7946,51",
        ),
        StructElement(
            id="2",
            name="Bottom Floor Construction",
            country="Germany",
            material="Precast Concrete Double Tee Floor Units",
            quantity="100",
            emissions="6341,36",
        ),
    ],
)


@require_http_methods(["GET", "POST", "DELETE"])
def building(request, building_id):
    global item

    context = {
        "items": item,
        "form_general_info": BuildingGeneralInformation
    }

    logger.info("Access list view with request: %s", request.method)

    building = None
    if building_id:
        try:
            building = Building.objects.get(pk=building_id)
            print("Found building: %s", building)
        except Building.DoesNotExist:
            return HttpResponse("Building not found", status=404)

    # General Info
    if request.method == "POST":
        new_item = request.POST.get("item")
        if new_item and len(item) < 5:
            logger.info("Add item: '%s' to list", new_item)
            item.append(new_item)
        return render(
            request, "pages/building/building_list/item.html", context
        )  # Partial update for POST

    elif request.method == "DELETE":
        item_to_delete = request.GET.get("component")
        item.components = [c for c in item.components if c.id != item_to_delete]
        return render(
            request, "pages/building/structural_info/assemblies_list.html", context
        )  # Partial update for DELETE

    else:
        context["form_general_info"] = BuildingGeneralInformation(instance=building)

    # Full page load for GET request
    logger.info("Serving full item list page for GET request")
    return render(request, "pages/building/building.html", context)
