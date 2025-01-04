import logging

from django.shortcuts import render
from django.views.decorators.http import require_http_methods

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
        context, form = handle_building_load(request, building_id, simulation=True)
        
        # disable the form fields and button
        for field in form.fields:
            form.fields[field].disabled = True
        
        form.helper.layout[4].flat_attrs = "disabled"

    context["form_general_info"] = form
    context["simulation"] = True
    # Full page load for GET request
    logger.info("Serving full item list page for GET request")
    return render(request, "pages/building/building_simulation.html", context)
 