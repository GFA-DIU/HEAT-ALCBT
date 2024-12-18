import logging

from cities_light.models import City
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required

from pages.models.building import Building


logger = logging.getLogger(__name__)


@login_required
@require_http_methods(["GET", "POST", "DELETE"])
def buildings_list(request):
    buildings = Building.objects.filter(created_by=request.user)
    context = {"buildings": buildings}

    logger.info("Access list view.")

    if request.method == "POST":
        new_item = request.POST.get("item")
        if new_item and len(buildings) < 5:
            logger.info("Add item: '%s' to list", new_item)
            buildings.append(new_item)
        return render(
            request, "pages/home/building_list/item.html", context
        )  # Partial update for POST

    elif request.method == "DELETE":
        building_id = request.GET.get("building_id")
        building_to_delete = get_object_or_404(Building, id=int(building_id))
        building_to_delete.delete()
        context = {"buildings": Building.objects.filter(created_by=request.user)}
        return render(request, "pages/home/buildings_list.html", context)
    
    elif request.GET.get('country'):
        country_id = request.GET.get('country')
        if country_id:
            cities = City.objects.filter(country_id=country_id).order_by('name')
            return render(request, 'pages/utils/city_list.html', {'cities': cities})
        
    # Full page load for GET request
    logger.info("Serving full item list page for GET request")
    return render(request, "pages/home/home.html", context)
