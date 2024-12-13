import ast
import logging
from django.apps import apps
from django.http import JsonResponse
import folium

from django.shortcuts import render

from django.views.decorators.http import require_http_methods

logger = logging.getLogger(__name__)

APP_NAME = "pages"

def create_building_markers(buildings):
    markers = []
    for building in buildings:
        markers.append(
            {
                "location": [building.latitude, building.longitude],
                "popup": f"<b>{building.name}</b><br>{building.address}",
            }
        )
    return markers

@require_http_methods(["GET"])
def map_view(request):
    logger.info("Access map view.")
    model = request.GET.get("model")
    # Check that the parameters are valid
    if not model:
        return JsonResponse({"error": "Missing 'model' parameter."}, status=400)

    try:
        model_ids = ast.literal_eval(request.GET.get("ids"))
    except (ValueError, SyntaxError):
        # Handle invalid or incorrectly formatted input
        return JsonResponse({"error": "Invalid 'ids' parameter. Must be a valid list of integers."}, status=400)

    # Retrieve the model class dynamically
    ModelClass = apps.get_model(app_label=APP_NAME, model_name=model)
    if not ModelClass:
        return JsonResponse({"error": "Missing 'model' parameter."}, status=400)

    if model_ids:
        objects = ModelClass.objects.filter(created_by=request.user, id__in=model_ids)
    else:
        objects = ModelClass.objects.filter(created_by=request.user)
    # Create the map
    f = folium.Figure(width=1000, height=500)
    folium_map = folium.Map(
        location=[24.021379, 58.640202], zoom_start=2, tiles="OpenStreetMap", height="60%"
    )
    for object in objects:
        if object.latitude and object.longitude:
            folium.Marker(
                location=[object.latitude, object.longitude],
                tooltip="Click me!",
                popup="Mt. Hood Meadows",
                icon=folium.Icon(icon="cloud"),
            ).add_to(folium_map)
    folium_map.add_to(f)
    # Render the map HTML
    map_html = f._repr_html_()  # This renders the full map HTML

    return render(request, "pages/home/map.html", {"map_html": map_html})
