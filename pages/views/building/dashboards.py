import logging
from django.http import JsonResponse

from django.shortcuts import render
from django.views.decorators.http import require_http_methods

from pages.views.building.building_dashboard import get_building_dashboard


logger = logging.getLogger(__name__)

APP_NAME = "pages"


@require_http_methods(["GET"])
def dashboard_view(request):
    logger.info("Access dashboard view.")
    model = request.GET.get("model")
    model_id = request.GET.get("id")
    dashboard_type = request.GET.get("dashboard_type")
    simulation = request.GET.get("simulation") == "True"
    # Check that the parameters are valid
    if not model:
        return JsonResponse({"error": "Missing 'model' parameter."}, status=400)


    if model == "building":
        dashboard_html = get_building_dashboard(request.user, model_id, dashboard_type, simulation)
        return render(request, "pages/building/dashboard/dashboard.html", {"dashboard_html": dashboard_html})