import logging

from dataclasses import dataclass, asdict
from django.shortcuts import render
from django.views.decorators.http import require_http_methods

from pages.forms.building_general_info import BuildingGeneralInformation

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
class Building:
    name: str
    country: str
    components: list[StructElement]


item = Building(
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
def building(request):
    global item
    context = {"items": item, "form": BuildingGeneralInformation}

    logger.info("Access list view with request: %s", request.method)

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

    # Full page load for GET request
    logger.info("Serving full item list page for GET request")
    return render(request, "pages/building/building.html", context)
