import logging

from django.db.models import Prefetch, Q
from django.http import HttpResponseServerError
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_http_methods

from pages.forms.building_general_info import BuildingGeneralInformation
from pages.models.assembly import DIMENSION_UNIT_MAPPING
from pages.models.building import Building, BuildingAssembly

from cities_light.models import City
from pages.scripts.dashboards.building_dashboard import building_dashboard
from pages.scripts.dashboards.impact_calculation import calculate_impacts
from pages.views.building.building import handle_building_load, handle_general_information_submit
from pages.views.building.building import handle_assembly_delete


logger = logging.getLogger(__name__)


@require_http_methods(["GET", "POST", "DELETE"])
def building_simulation(request, building_id = None):
    logger.info("Building Simulation - Request method: %s, user: %s", request.method, request.user)

    if request.method == "DELETE":
        return handle_assembly_delete(request, building_id)

    # Full reload
    elif building_id:
        context, form = handle_building_load(request, building_id)

    context["form_general_info"] = form
    # Full page load for GET request
    logger.info("Serving full item list page for GET request")
    return render(request, "pages/building/building.html", context)
 