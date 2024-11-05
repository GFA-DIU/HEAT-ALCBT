import logging

from dataclasses import dataclass, asdict
from django.shortcuts import render
from django.views.decorators.http import require_http_methods

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
    name="Building 1",
    country="India",
    components=[
        StructElement(
            id="1",
            name="Component 1",
            country="Germany",
            material="wood",
            quantity="20",
            emissions="30",
        ),
        StructElement(
            id="2",
            name="Component 2",
            country="Germany",
            material="clay",
            quantity="10",
            emissions="15",
        ),
    ],
)


@require_http_methods(["GET", "POST", "DELETE"])
def building(request):
    global item
    context = {"items": item}

    logger.info("Access list view with request: %s", request.method)

    if request.method == "POST":
        new_item = request.POST.get("item")
        if new_item and len(item) < 5:
            logger.info("Add item: '%s' to list", new_item)
            item.append(new_item)
        return render(
            request, "pages/home/building_list/item.html", context
        )  # Partial update for POST

    elif request.method == "DELETE":
        item_to_delete = request.GET.get("component")
        item.components = [c for c in item.components if c.id != item_to_delete]
        return render(
            request, "pages/building/building_list/building_item.html", context
        )  # Partial update for DELETE

    # Full page load for GET request
    logger.info("Serving full item list page for GET request")
    return render(request, "pages/building/building.html", context)
