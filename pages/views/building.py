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
        "building_id": building_id,
    }

    logger.info("Access list view with request: %s", request.method)

    building = None
    try:
        building = Building.objects.get(pk=building_id)
        print("Found building: %s", building)
    except Building.DoesNotExist:
        return HttpResponse("Building not found", status=404)

    # General Info
    if request.method == "POST" and request.POST.get('action') == "general_information":
        form = BuildingGeneralInformation(request.POST, instance=building)  # Bind form to instance
        if form.is_valid():
            print("these fields changed", form.changed_data)
            updated_building = form.save()
            print("Building updated in DB:", updated_building)
        else:
            print("Form is invalid")
            print("Errors:", form.errors)

    elif request.method == "DELETE":
        item_to_delete = request.GET.get("component")
        item.components = [c for c in item.components if c.id != item_to_delete]
        return render(
            request, "pages/building/structural_info/assemblies_list.html", context
        )  # Partial update for DELETE

    else:
        form = BuildingGeneralInformation(instance=building)

    context["form_general_info"] = form
    # Full page load for GET request
    logger.info("Serving full item list page for GET request")
    return render(request, "pages/building/building.html", context)
